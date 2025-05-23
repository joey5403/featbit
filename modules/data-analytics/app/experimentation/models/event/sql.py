from typing import Any, Dict, List

import pandas as pd

from app.clickhouse.models.event.sql import event_table_name
from app.mongodb.models.event.util import get_events_sample_from_mongod

# ClickHouse
FLAG_EVENTS_CTE_CH = f"""flag_events as
(
SELECT tag_0 AS target_user, tag_1 AS variation
FROM {event_table_name()}
WHERE distinct_id = %(flag_id)s
AND event = 'FlagValue'
AND env_id = %(env_id)s
AND timestamp > %(start)s
AND timestamp < %(end)s
AND tag_2 = 'true'
)"""

CUSTOM_EVENTS_CTE_CH = f"""custom_events as
(
SELECT tag_0 AS target_user, tag_0 AS exposure_user
FROM {event_table_name()}
WHERE distinct_id = %(event_name)s
AND event = %(event)s
AND env_id = %(env_id)s
AND timestamp > %(start)s
AND timestamp < %(end)s
)"""

CUSTOM_EVENTS_WITH_WEIGHT_CTE_CH = f"""custom_events as
(
SELECT tag_0 AS target_user, toFloat64(tag_1) AS exposure_weight
FROM {event_table_name()}
WHERE distinct_id = %(event_name)s
AND event = %(event)s
AND env_id = %(env_id)s
AND timestamp > %(start)s
AND timestamp < %(end)s
)"""

VARIATION_CTE_CH = """variations as
(
SELECT target_user, max(if(empty(exposure_user),0,1.0)) AS exposure_weight, variation
FROM flag_events GLOBAL LEFT JOIN custom_events USING target_user
GROUP BY target_user, variation
)"""

VARIATION_WITH_WEIGHT_CTE_CH = """variations as
(
SELECT target_user, sum(exposure_weight) AS exposure_weight, variation
FROM flag_events GLOBAL INNER JOIN custom_events USING target_user
GROUP BY target_user, variation
)"""

GET_BINOMIAL_VARS_SQL = """SELECT count(target_user), sum(exposure_weight), variation
FROM variations
GROUP BY variation
ORDER BY variation"""

GET_NUMERIC_VARS_SQL_CH = """SELECT count(target_user), sum(exposure_weight), avg(exposure_weight), varSamp(exposure_weight), variation
FROM variations
GROUP BY variation
ORDER BY variation"""


GET_BINOMIAL_TEST_VARS_SQL_CH = f"""WITH
{FLAG_EVENTS_CTE_CH},
{CUSTOM_EVENTS_CTE_CH},
{VARIATION_CTE_CH}
{GET_BINOMIAL_VARS_SQL}"""

GET_NUMERIC_TEST_VARS_SQL_CH = f"""WITH
{FLAG_EVENTS_CTE_CH},
{CUSTOM_EVENTS_WITH_WEIGHT_CTE_CH},
{VARIATION_WITH_WEIGHT_CTE_CH}
{GET_NUMERIC_VARS_SQL_CH}"""

# PG
FLAG_EVENTS_CTE_PG = f"""flag_events as
(
SELECT properties->>'tag_0' AS target_user, properties->>'tag_1' AS variation
FROM events
WHERE distinct_id = %(flag_id)s
AND event = 'FlagValue'
AND env_id = %(env_id)s
AND timestamp > %(start)s
AND timestamp < %(end)s
AND properties->>'tag_2' = 'true'
)"""

CUSTOM_EVENTS_CTE_PG = f"""custom_events as
(
SELECT properties->>'tag_0' AS target_user, properties->>'tag_0' AS exposure_user
FROM events
WHERE distinct_id = %(event_name)s
AND event = %(event)s
AND env_id = %(env_id)s
AND timestamp > %(start)s
AND timestamp < %(end)s
)"""

VARIATION_CTE_PG = """variations as
(
SELECT fe.target_user, max(CASE WHEN ce.exposure_user IS NULL THEN 0 ELSE 1.0 END) AS exposure_weight, fe.variation
FROM flag_events fe LEFT JOIN custom_events ce ON fe.target_user = ce.target_user
GROUP BY fe.target_user, fe.variation
)"""

VARIATION_WITH_WEIGHT_CTE_PG = """variations as
(
SELECT fe.target_user, SUM(ce.exposure_weight) AS exposure_weight, fe.variation
FROM flag_events fe INNER JOIN custom_events ce ON fe.target_user = ce.target_user
GROUP BY fe.target_user, fe.variation
)"""

CUSTOM_EVENTS_WITH_WEIGHT_CTE_PG = f"""custom_events as
(
SELECT properties->>'tag_0' AS target_user, CAST(properties->>'tag_1' AS FLOAT8) AS exposure_weight
FROM events
WHERE distinct_id = %(event_name)s
AND event = %(event)s
AND env_id = %(env_id)s
AND timestamp > %(start)s
AND timestamp < %(end)s
)"""

GET_NUMERIC_VARS_SQL_PG = """SELECT count(target_user), sum(exposure_weight), avg(exposure_weight), VAR_SAMP(exposure_weight), variation
FROM variations
GROUP BY variation
ORDER BY variation"""

GET_BINOMIAL_TEST_VARS_SQL_PG = f"""WITH
{FLAG_EVENTS_CTE_PG},
{CUSTOM_EVENTS_CTE_PG},
{VARIATION_CTE_PG}
{GET_BINOMIAL_VARS_SQL}"""

GET_NUMERIC_TEST_VARS_SQL_PG = f"""WITH
{FLAG_EVENTS_CTE_PG},
{CUSTOM_EVENTS_WITH_WEIGHT_CTE_PG},
{VARIATION_WITH_WEIGHT_CTE_PG}
{GET_NUMERIC_VARS_SQL_PG}"""


# MongoDB
def _query_ff_events_sample_from_mongod(query_params: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            '$match': {
                'event': 'FlagValue',
                'env_id': query_params['env_id'],
                'distinct_id': query_params['flag_id'],
                'timestamp': {
                    '$gt': query_params['start'],
                    '$lt': query_params['end']
                },
                "properties.sendToExperiment": True
            }
        }, {
            '$project': {
                '_id': 0,
                'user_key': '$properties.userKeyId',
                'variation': '$properties.variationId'
            }
        }
    ]


def _query_metric_events_sample_from_mongod(query_params: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            '$match': {
                'event': query_params['event'],
                'env_id': query_params['env_id'],
                'distinct_id': query_params['event_name'],
                'timestamp': {
                    '$gt': query_params['start'],
                    '$lt': query_params['end']
                },
            }
        }, {
            '$project': {
                '_id': 0,
                'user_key': '$properties.user.keyId',
                'weight': '$properties.numericValue'
            }
        }
    ]


def cal_experiment_vars_from_mongod(query_params: Dict[str, Any], binomial_test: bool):
    df_ff_events = get_events_sample_from_mongod(_query_ff_events_sample_from_mongod(query_params), cols=['user_key', 'variation'])
    if df_ff_events.empty:
        return []
    df_metric_events = get_events_sample_from_mongod(_query_metric_events_sample_from_mongod(query_params), cols=['user_key', 'weight'])
    if df_metric_events.empty:
        df_metric_events = pd.DataFrame({'user_key': pd.Series(dtype='str'),
                                         'weight': pd.Series(dtype='float')})
    elif binomial_test:
        df_metric_events["weight"] = 1.0

    df = df_ff_events.merge(df_metric_events, on='user_key', how='left' if binomial_test else 'inner') \
        .fillna(0)
    if binomial_test:
        df = df.groupby(['user_key', 'variation']) \
            .max() \
            .reset_index()
        df = df.groupby('variation') \
            .agg(uniq=('user_key', lambda x: float(x.nunique())), sum=('weight', lambda x: x.sum())) \
            .sort_values('variation') \
            .reset_index()
        for count, exposure, var_key in df[['uniq', 'sum', 'variation']].values.tolist():
            yield count, exposure, var_key
    else:
        df = df.groupby(['user_key', 'variation']) \
            .sum() \
            .reset_index()
        df = df = df.groupby('variation') \
            .agg(uniq=('user_key', lambda x: float(x.nunique())), sum=('weight', lambda x: x.sum()),
                 avg=('weight', lambda x: x.mean()), var=('weight', lambda x: x.var(ddof=1))) \
            .sort_values('variation') \
            .reset_index()
        for count, exposure, mean_sample, var_sample, var_key in df[['uniq', 'sum', 'avg', 'var', 'variation']].values.tolist():
            yield count, exposure, mean_sample, var_sample, var_key

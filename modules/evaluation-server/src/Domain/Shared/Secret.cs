namespace Domain.Shared;

public class Secret
{
    public string Type { get; set; } = string.Empty;

    public string ProjectKey { get; set; } = string.Empty;

    public Guid EnvId { get; set; } = Guid.Empty;

    public string EnvKey { get; set; } = string.Empty;

    // for dapper deserialization
    public Secret()
    {
    }

    public Secret(string type, string projectKey, Guid envId, string envKey)
    {
        Type = type;
        ProjectKey = projectKey;
        EnvId = envId;
        EnvKey = envKey;
    }

    public static bool TryParse(string? secretString, out Guid envId)
    {
        // secret string format: {encodedGuid}{encodedEnvId}
        // encoded guid's length will always be 22, see GuidHelper.Encode

        envId = Guid.Empty;
        if (string.IsNullOrWhiteSpace(secretString) || secretString.Length != 44)
        {
            return false;
        }

        var encodedEnvId = secretString.AsSpan().Slice(22, 22);
        envId = GuidHelper.Decode(encodedEnvId);

        return envId != Guid.Empty;
    }
}
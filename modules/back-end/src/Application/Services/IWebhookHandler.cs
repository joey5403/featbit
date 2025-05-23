using Domain.AuditLogs;
using Domain.FeatureFlags;
using Domain.Segments;

namespace Application.Services;

public interface IWebhookHandler
{
    Task HandleAsync(FeatureFlag flag, DataChange dataChange, Guid operatorId);

    Task HandleAsync(Guid envId, Segment segment, DataChange dataChange, Guid operatorId);
}

public interface IGeneralWebhookHandler : IWebhookHandler;

public interface IScopedWebhookHandler : IWebhookHandler;
using SmartParking.Application.DTOs.PlateScans;

namespace SmartParking.Application.Interfaces;

public interface IPlateScanService
{
    Task<IReadOnlyList<PlateScanResponse>> GetAllAsync(string? search = null);
    Task<PlateScanResponse?> GetByIdAsync(long id);
    Task<PlateScanResponse> CreateAsync(CreatePlateScanRequest request);
    Task<bool> DeleteAsync(long id);
    Task<PlateScanStatsResponse> GetStatsAsync();
}

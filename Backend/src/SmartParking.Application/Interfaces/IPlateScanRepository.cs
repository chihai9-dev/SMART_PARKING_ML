using SmartParking.Domain.Entities;

namespace SmartParking.Application.Interfaces;

public interface IPlateScanRepository
{
    Task<IReadOnlyList<PlateScan>> GetAllAsync(string? search = null);
    Task<PlateScan?> GetByIdAsync(long id);
    Task<long> CreateAsync(PlateScan scan);
    Task<bool> DeleteAsync(long id);
}

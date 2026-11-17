using SmartParking.Application.DTOs.PlateScans;
using SmartParking.Application.Interfaces;
using SmartParking.Domain.Entities;

namespace SmartParking.Application.Services;

public class PlateScanService : IPlateScanService
{
    private readonly IPlateScanRepository _repository;

    public PlateScanService(IPlateScanRepository repository)
    {
        _repository = repository;
    }

    public async Task<IReadOnlyList<PlateScanResponse>> GetAllAsync(string? search = null)
    {
        var scans = await _repository.GetAllAsync(search);
        return scans.Select(MapToResponse).ToList();
    }

    public async Task<PlateScanResponse?> GetByIdAsync(long id)
    {
        var scan = await _repository.GetByIdAsync(id);
        return scan == null ? null : MapToResponse(scan);
    }

    public async Task<PlateScanResponse> CreateAsync(CreatePlateScanRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.Plate))
            throw new ArgumentException("Biển số xe không được để trống.");
        if (request.Confidence is < 0 or > 1)
            throw new ArgumentOutOfRangeException(nameof(request.Confidence), "Độ tin cậy phải nằm trong khoảng 0 đến 1.");
        if (request.PlateColorConfidence is < 0 or > 1)
            throw new ArgumentOutOfRangeException(nameof(request.PlateColorConfidence), "Độ tin cậy màu phải nằm trong khoảng 0 đến 1.");

        var scan = new PlateScan
        {
            Plate = request.Plate.Trim().ToUpper(),
            Confidence = request.Confidence ?? 1.0,
            ImagePath = request.ImagePath,
            CropImagePath = request.CropImagePath,
            PlateColorCode = request.PlateColorCode,
            PlateColorLabel = request.PlateColorLabel,
            PlateColorConfidence = request.PlateColorConfidence,
            ScanTime = request.ScanTime ?? DateTime.Now,
            Note = request.Note,
            CreatedAt = DateTime.Now
        };

        var newId = await _repository.CreateAsync(scan);
        scan.ScanId = newId;
        return MapToResponse(scan);
    }

    public Task<bool> DeleteAsync(long id) => _repository.DeleteAsync(id);

    public async Task<PlateScanStatsResponse> GetStatsAsync()
    {
        var all = await _repository.GetAllAsync();
        var today = DateTime.Today;
        var total = all.Count;
        var todayCount = all.Count(s => s.ScanTime.Date == today);
        var avgConf = total > 0 ? all.Average(s => s.Confidence) : 0.0;

        return new PlateScanStatsResponse
        {
            TotalScans = total,
            TodayScans = todayCount,
            AverageConfidence = Math.Round(avgConf, 4)
        };
    }

    private static PlateScanResponse MapToResponse(PlateScan scan) => new()
    {
        ScanId = scan.ScanId,
        Plate = scan.Plate,
        Confidence = scan.Confidence,
        ImagePath = scan.ImagePath,
        CropImagePath = scan.CropImagePath,
        PlateColorCode = scan.PlateColorCode,
        PlateColorLabel = scan.PlateColorLabel,
        PlateColorConfidence = scan.PlateColorConfidence,
        ScanTime = scan.ScanTime,
        Note = scan.Note,
        CreatedAt = scan.CreatedAt
    };
}

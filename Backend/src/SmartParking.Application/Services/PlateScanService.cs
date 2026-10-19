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
        {
            throw new ArgumentException("Biển số xe không được để trống.");
        }

        var scan = new PlateScan
        {
            Plate = request.Plate.Trim().ToUpper(),
            VehicleType = string.IsNullOrWhiteSpace(request.VehicleType) ? "Motorbike" : request.VehicleType.Trim(),
            Confidence = request.Confidence > 0 ? request.Confidence : 1.0,
            ImagePath = request.ImagePath,
            CropImagePath = request.CropImagePath,
            ScanTime = request.ScanTime ?? DateTime.Now,
            Note = request.Note,
            CreatedAt = DateTime.Now
        };

        var newId = await _repository.CreateAsync(scan);
        scan.ScanId = newId;

        return MapToResponse(scan);
    }

    public async Task<bool> DeleteAsync(long id)
    {
        return await _repository.DeleteAsync(id);
    }

    public async Task<PlateScanStatsResponse> GetStatsAsync()
    {
        var all = await _repository.GetAllAsync();
        var today = DateTime.Today;

        var total = all.Count;
        var todayCount = all.Count(s => s.ScanTime.Date == today);
        var motorbikes = all.Count(s => s.VehicleType.Equals("Motorbike", StringComparison.OrdinalIgnoreCase));
        var cars = all.Count(s => s.VehicleType.Equals("Car", StringComparison.OrdinalIgnoreCase));
        var avgConf = total > 0 ? all.Average(s => s.Confidence) : 0.0;

        return new PlateScanStatsResponse
        {
            TotalScans = total,
            TodayScans = todayCount,
            Motorbikes = motorbikes,
            Cars = cars,
            AverageConfidence = Math.Round(avgConf, 4)
        };
    }

    private static PlateScanResponse MapToResponse(PlateScan scan)
    {
        return new PlateScanResponse
        {
            ScanId = scan.ScanId,
            Plate = scan.Plate,
            VehicleType = scan.VehicleType,
            Confidence = scan.Confidence,
            ImagePath = scan.ImagePath,
            CropImagePath = scan.CropImagePath,
            ScanTime = scan.ScanTime,
            Note = scan.Note,
            CreatedAt = scan.CreatedAt
        };
    }
}

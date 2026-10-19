namespace SmartParking.Application.DTOs.PlateScans;

public class PlateScanResponse
{
    public long ScanId { get; set; }
    public string Plate { get; set; } = string.Empty;
    public string VehicleType { get; set; } = string.Empty;
    public double Confidence { get; set; }
    public string? ImagePath { get; set; }
    public string? CropImagePath { get; set; }
    public DateTime ScanTime { get; set; }
    public string? Note { get; set; }
    public DateTime CreatedAt { get; set; }
}

public class PlateScanStatsResponse
{
    public int TotalScans { get; set; }
    public int TodayScans { get; set; }
    public int Motorbikes { get; set; }
    public int Cars { get; set; }
    public double AverageConfidence { get; set; }
}

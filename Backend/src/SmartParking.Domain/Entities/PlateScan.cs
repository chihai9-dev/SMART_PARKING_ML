namespace SmartParking.Domain.Entities;

public class PlateScan
{
    public long ScanId { get; set; }
    public string Plate { get; set; } = string.Empty;
    public string VehicleType { get; set; } = "Motorbike";
    public double Confidence { get; set; } = 1.0;
    public string? ImagePath { get; set; }
    public string? CropImagePath { get; set; }
    public DateTime ScanTime { get; set; } = DateTime.UtcNow;
    public string? Note { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}

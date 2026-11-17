namespace SmartParking.Domain.Entities;

public class PlateScan
{
    public long ScanId { get; set; }
    public string Plate { get; set; } = string.Empty;
    public double Confidence { get; set; }
    public string? ImagePath { get; set; }
    public string? CropImagePath { get; set; }
    public string? PlateColorCode { get; set; }
    public string? PlateColorLabel { get; set; }
    public double? PlateColorConfidence { get; set; }
    public DateTime ScanTime { get; set; } = DateTime.UtcNow;
    public string? Note { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}

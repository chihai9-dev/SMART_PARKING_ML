namespace SmartParking.Application.DTOs.PlateScans;

public class CreatePlateScanRequest
{
    public string Plate { get; set; } = string.Empty;
    public double? Confidence { get; set; }
    public string? ImagePath { get; set; }
    public string? CropImagePath { get; set; }
    public string? PlateColorCode { get; set; }
    public string? PlateColorLabel { get; set; }
    public double? PlateColorConfidence { get; set; }
    public DateTime? ScanTime { get; set; }
    public string? Note { get; set; }
    public string? ColorCode { get; set; }
}

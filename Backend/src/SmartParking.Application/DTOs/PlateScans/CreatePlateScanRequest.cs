namespace SmartParking.Application.DTOs.PlateScans;

public class CreatePlateScanRequest
{
    public string Plate { get; set; } = string.Empty;
    public string VehicleType { get; set; } = "Motorbike";
    public double Confidence { get; set; } = 1.0;
    public string? ImagePath { get; set; }
    public string? CropImagePath { get; set; }
    public DateTime? ScanTime { get; set; }
    public string? Note { get; set; }
}

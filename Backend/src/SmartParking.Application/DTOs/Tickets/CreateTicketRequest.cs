namespace SmartParking.Application.DTOs.Tickets;

public class CreateTicketRequest
{
    public string Plate { get; set; } = string.Empty;

    public string VehicleType { get; set; } = "Motorbike";

    public DateTime? EntryTime { get; set; }

    public string? EntryImagePath { get; set; }

    public string? PlateImagePath { get; set; }
}
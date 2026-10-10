using SmartParking.Domain.Enums;

namespace SmartParking.Application.DTOs.Tickets;

public class TicketResponse
{
    public long TicketId { get; set; }

    public string TicketCode { get; set; } = string.Empty;

    public string Plate { get; set; } = string.Empty;

    public string VehicleType { get; set; } = string.Empty;

    public DateTime EntryTime { get; set; }

    public string? EntryImagePath { get; set; }

    public string? PlateImagePath { get; set; }

    public DateTime? ExitTime { get; set; }

    public string? ExitImagePath { get; set; }

    public TicketStatus Status { get; set; }

    public decimal PenaltyAmount { get; set; }

    public DateTime CreatedAt { get; set; }
}

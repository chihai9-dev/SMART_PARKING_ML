using SmartParking.Application.DTOs.Tickets;
using SmartParking.Application.Interfaces;
using SmartParking.Domain.Entities;
using SmartParking.Domain.Enums;

namespace SmartParking.Application.Services;

public class TicketService : ITicketService
{
    private readonly ITicketRepository _repository;

    public TicketService(ITicketRepository repository)
    {
        _repository = repository;
    }

    public async Task<IReadOnlyList<TicketResponse>> GetAllAsync()
    {
        var tickets = await _repository.GetAllAsync();

        return tickets.Select(ToResponse).ToList();
    }

    public async Task<TicketResponse?> GetByIdAsync(long id)
    {
        var ticket = await _repository.GetByIdAsync(id);

        return ticket == null
            ? null
            : ToResponse(ticket);
    }

    public async Task<TicketResponse?> GetOpenByPlateAsync(
        string plate)
    {
        plate = plate.Trim().ToUpperInvariant();

        if (string.IsNullOrWhiteSpace(plate))
        {
            return null;
        }

        var ticket =
            await _repository.GetOpenByPlateAsync(plate);

        return ticket == null
            ? null
            : ToResponse(ticket);
    }

    public async Task<TicketResponse> CreateEntryAsync(
        CreateTicketRequest request)
    {
        var plate = request.Plate.Trim().ToUpperInvariant();

        if (string.IsNullOrWhiteSpace(plate))
        {
            throw new ArgumentException(
                "Biển số xe không được để trống.");
        }

        var existing =
            await _repository.GetOpenByPlateAsync(plate);

        if (existing != null)
        {
            throw new InvalidOperationException(
                "Xe này đang có vé gửi chưa đóng.");
        }

        var now = request.EntryTime ?? DateTime.Now;

        var ticket = new Ticket
        {
            TicketCode =
                $"SP-{now:yyyyMMdd-HHmmssfff}",

            Plate = plate,

            VehicleType =
                string.IsNullOrWhiteSpace(request.VehicleType)
                    ? "Motorbike"
                    : request.VehicleType,

            EntryTime = now,

            EntryImagePath = request.EntryImagePath,

            PlateImagePath = request.PlateImagePath,

            Status = TicketStatus.Open,

            PenaltyAmount = 0,

            CreatedAt = DateTime.Now
        };

        ticket.TicketId =
            await _repository.CreateAsync(ticket);

        return ToResponse(ticket);
    }

    public async Task<TicketResponse?> CloseExitAsync(
        long id,
        string? exitImagePath,
        decimal penaltyAmount,
        int status)
    {
        var ticket =
            await _repository.GetByIdAsync(id);

        if (ticket == null ||
            ticket.Status != TicketStatus.Open)
        {
            return null;
        }

        var exitTime = DateTime.Now;

        var updated =
            await _repository.CloseAsync(
                id,
                exitTime,
                exitImagePath,
                penaltyAmount,
                status);

        if (!updated)
        {
            return null;
        }

        ticket.ExitTime = exitTime;

        ticket.ExitImagePath = exitImagePath;

        ticket.PenaltyAmount = penaltyAmount;

        ticket.Status = (TicketStatus)status;

        return ToResponse(ticket);
    }

    private static TicketResponse ToResponse(
        Ticket ticket)
    {
        return new TicketResponse
        {
            TicketId = ticket.TicketId,

            TicketCode = ticket.TicketCode,

            Plate = ticket.Plate,

            VehicleType = ticket.VehicleType,

            EntryTime = ticket.EntryTime,

            EntryImagePath = ticket.EntryImagePath,

            PlateImagePath = ticket.PlateImagePath,

            ExitTime = ticket.ExitTime,

            ExitImagePath = ticket.ExitImagePath,

            Status = ticket.Status,

            PenaltyAmount = ticket.PenaltyAmount,

            CreatedAt = ticket.CreatedAt
        };
    }
}
using SmartParking.Application.DTOs.Tickets;

namespace SmartParking.Application.Interfaces;

public interface ITicketService
{
    Task<IReadOnlyList<TicketResponse>> GetAllAsync();

    Task<TicketResponse?> GetByIdAsync(long id);

    Task<TicketResponse?> GetOpenByPlateAsync(string plate);

    Task<TicketResponse> CreateEntryAsync(CreateTicketRequest request);

    Task<TicketResponse?> CloseExitAsync(
        long id,
        string? exitImagePath,
        decimal penaltyAmount,
        int status);
}
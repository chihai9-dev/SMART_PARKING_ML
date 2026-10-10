using SmartParking.Domain.Entities;

namespace SmartParking.Application.Interfaces;

public interface ITicketRepository
{
    Task<IReadOnlyList<Ticket>> GetAllAsync();

    Task<Ticket?> GetByIdAsync(long id);

    Task<Ticket?> GetOpenByPlateAsync(string plate);

    Task<long> CreateAsync(Ticket ticket);

    Task<bool> CloseAsync(
        long id,
        DateTime exitTime,
        string? exitImagePath,
        decimal penaltyAmount,
        int status);
}
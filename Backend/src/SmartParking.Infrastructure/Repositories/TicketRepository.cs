using Dapper;
using SmartParking.Application.Interfaces;
using SmartParking.Domain.Entities;
using SmartParking.Domain.Enums;
using SmartParking.Infrastructure.Data;

namespace SmartParking.Infrastructure.Repositories;

public class TicketRepository : ITicketRepository
{
    private readonly DbConnectionFactory _factory;

    public TicketRepository(DbConnectionFactory factory)
    {
        _factory = factory;
    }

    public async Task<IReadOnlyList<Ticket>> GetAllAsync()
    {
        const string sql = """
            SELECT TicketId,
                   TicketCode,
                   Plate,
                   VehicleType,
                   EntryTime,
                   EntryImagePath,
                   PlateImagePath,
                   ExitTime,
                   ExitImagePath,
                   Status,
                   PenaltyAmount,
                   CreatedAt
            FROM Tickets
            ORDER BY TicketId DESC;
            """;

        using var db = _factory.CreateConnection();

        var rows = await db.QueryAsync<Ticket>(sql);

        return rows.ToList();
    }

    public async Task<Ticket?> GetByIdAsync(long id)
    {
        const string sql = """
            SELECT TicketId,
                   TicketCode,
                   Plate,
                   VehicleType,
                   EntryTime,
                   EntryImagePath,
                   PlateImagePath,
                   ExitTime,
                   ExitImagePath,
                   Status,
                   PenaltyAmount,
                   CreatedAt
            FROM Tickets
            WHERE TicketId = @Id;
            """;

        using var db = _factory.CreateConnection();

        return await db.QuerySingleOrDefaultAsync<Ticket>(
            sql,
            new
            {
                Id = id
            });
    }

    public async Task<Ticket?> GetOpenByPlateAsync(
        string plate)
    {
        const string sql = """
            SELECT TOP 1
                   TicketId,
                   TicketCode,
                   Plate,
                   VehicleType,
                   EntryTime,
                   EntryImagePath,
                   PlateImagePath,
                   ExitTime,
                   ExitImagePath,
                   Status,
                   PenaltyAmount,
                   CreatedAt
            FROM Tickets
            WHERE Plate = @Plate
              AND Status = @Status
            ORDER BY TicketId DESC;
            """;

        using var db = _factory.CreateConnection();

        return await db.QuerySingleOrDefaultAsync<Ticket>(
            sql,
            new
            {
                Plate = plate,
                Status = (int)TicketStatus.Open
            });
    }

    public async Task<long> CreateAsync(Ticket ticket)
    {
        const string sql = """
            INSERT INTO Tickets
            (
                TicketCode,
                Plate,
                VehicleType,
                EntryTime,
                EntryImagePath,
                PlateImagePath,
                Status,
                PenaltyAmount,
                CreatedAt
            )
            OUTPUT INSERTED.TicketId
            VALUES
            (
                @TicketCode,
                @Plate,
                @VehicleType,
                @EntryTime,
                @EntryImagePath,
                @PlateImagePath,
                @Status,
                @PenaltyAmount,
                @CreatedAt
            );
            """;

        using var db = _factory.CreateConnection();

        return await db.ExecuteScalarAsync<long>(
            sql,
            ticket);
    }

    public async Task<bool> CloseAsync(
        long id,
        DateTime exitTime,
        string? exitImagePath,
        decimal penaltyAmount,
        int status)
    {
        const string sql = """
            UPDATE Tickets
            SET ExitTime = @ExitTime,
                ExitImagePath = @ExitImagePath,
                Status = @Status,
                PenaltyAmount = @PenaltyAmount
            WHERE TicketId = @Id
              AND Status = @OpenStatus;
            """;

        using var db = _factory.CreateConnection();

        var affected = await db.ExecuteAsync(
            sql,
            new
            {
                Id = id,
                ExitTime = exitTime,
                ExitImagePath = exitImagePath,
                Status = status,
                PenaltyAmount = penaltyAmount,
                OpenStatus = (int)TicketStatus.Open
            });

        return affected > 0;
    }
}
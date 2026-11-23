using Dapper;
using SmartParking.Application.Interfaces;
using SmartParking.Domain.Entities;
using SmartParking.Infrastructure.Data;

namespace SmartParking.Infrastructure.Repositories;

public class PlateScanRepository : IPlateScanRepository
{
    private readonly DbConnectionFactory _factory;

    public PlateScanRepository(DbConnectionFactory factory)
    {
        _factory = factory;
    }

    public async Task<IReadOnlyList<PlateScan>> GetAllAsync(string? search = null)
    {
        string sql = """
            SELECT ScanId, Plate, Confidence, ImagePath, CropImagePath,
                   PlateColorCode, PlateColorLabel, PlateColorConfidence,
                   ScanTime, Note, ColorCode, CreatedAt
            FROM PlateScans
            """;
        if (!string.IsNullOrWhiteSpace(search))
            sql += " WHERE Plate LIKE @Search ";
        sql += " ORDER BY ScanId DESC;";

        using var db = _factory.CreateConnection();
        var rows = await db.QueryAsync<PlateScan>(sql, new { Search = $"%{search}%" });
        return rows.ToList();
    }

    public async Task<PlateScan?> GetByIdAsync(long id)
    {
        const string sql = """
            SELECT ScanId, Plate, Confidence, ImagePath, CropImagePath,
                   PlateColorCode, PlateColorLabel, PlateColorConfidence,
                   ScanTime, Note, ColorCode, CreatedAt
            FROM PlateScans
            WHERE ScanId = @Id;
            """;
        using var db = _factory.CreateConnection();
        return await db.QuerySingleOrDefaultAsync<PlateScan>(sql, new { Id = id });
    }

    public async Task<long> CreateAsync(PlateScan scan)
    {
        const string sql = """
            INSERT INTO PlateScans
                (Plate, Confidence, ImagePath, CropImagePath,
                 PlateColorCode, PlateColorLabel, PlateColorConfidence,
                 ScanTime, Note, ColorCode, CreatedAt)
            OUTPUT INSERTED.ScanId
            VALUES
                (@Plate, @Confidence, @ImagePath, @CropImagePath,
                 @PlateColorCode, @PlateColorLabel, @PlateColorConfidence,
                 @ScanTime, @Note, @ColorCode, @CreatedAt);
            """;
        using var db = _factory.CreateConnection();
        return await db.ExecuteScalarAsync<long>(sql, scan);
    }

    public async Task<bool> DeleteAsync(long id)
    {
        const string sql = "DELETE FROM PlateScans WHERE ScanId = @Id;";
        using var db = _factory.CreateConnection();
        return await db.ExecuteAsync(sql, new { Id = id }) > 0;
    }
}

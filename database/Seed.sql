
/*
    SmartParking - Seed Data
    SQL Server

    Du lieu mau:
    1. SP-SEED-OPEN-001: Ve dang gui.
    2. SP-SEED-CLOSED-001: Ve da dong.

    Co the chay lai script ma khong chen trung
    cac ve mau da ton tai.
*/

USE [SmartParking];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

DECLARE @Now DATETIME2(3) = SYSDATETIME();

BEGIN TRY
    BEGIN TRANSACTION;

    -- 1. Ve mau dang gui
    IF NOT EXISTS
    (
        SELECT 1
        FROM dbo.Tickets
        WHERE TicketCode = N'SP-SEED-OPEN-001'
    )
    BEGIN
        INSERT INTO dbo.Tickets
        (
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
        )
        VALUES
        (
            N'SP-SEED-OPEN-001',
            N'DEMO-001',
            N'Motorbike',
            DATEADD(MINUTE, -20, @Now),
            NULL,
            NULL,
            NULL,
            NULL,
            1,
            0,
            DATEADD(MINUTE, -20, @Now)
        );
    END;

    -- 2. Ve mau da dong
    IF NOT EXISTS
    (
        SELECT 1
        FROM dbo.Tickets
        WHERE TicketCode = N'SP-SEED-CLOSED-001'
    )
    BEGIN
        INSERT INTO dbo.Tickets
        (
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
        )
        VALUES
        (
            N'SP-SEED-CLOSED-001',
            N'DEMO-002',
            N'Motorbike',
            DATEADD(HOUR, -2, @Now),
            NULL,
            NULL,
            DATEADD(HOUR, -1, @Now),
            NULL,
            2,
            0,
            DATEADD(HOUR, -2, @Now)
        );
    END;

    COMMIT TRANSACTION;

    PRINT N'SmartParking seed data completed.';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    THROW;
END CATCH;
GO

-- 3. Kiem tra du lieu mau
SELECT
    TicketId,
    TicketCode,
    Plate,
    VehicleType,
    EntryTime,
    ExitTime,
    Status,
    PenaltyAmount,
    CreatedAt
FROM dbo.Tickets
WHERE TicketCode IN
(
    N'SP-SEED-OPEN-001',
    N'SP-SEED-CLOSED-001'
)
ORDER BY TicketId DESC;
GO

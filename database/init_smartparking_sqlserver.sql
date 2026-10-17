-- =======================================================
-- KHOI TAO DATABASE VA BANG CHO SMART PARKING (.NET BACKEND)
-- Chay file nay trong VS Code bang SQLTools hoac SSMS
-- =======================================================

-- 1. Tao Database neu chua co
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'SmartParking')
BEGIN
    CREATE DATABASE SmartParking;
    PRINT N'Da tao Database SmartParking thanh cong!';
END
ELSE
BEGIN
    PRINT N'Database SmartParking da ton tai.';
END
GO

-- 2. Chuyen sang Database SmartParking
USE SmartParking;
GO

-- 3. Tao bang Tickets
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Tickets')
BEGIN
    CREATE TABLE Tickets (
        TicketId BIGINT IDENTITY(1,1) PRIMARY KEY,
        TicketCode NVARCHAR(100) NOT NULL,
        Plate NVARCHAR(50) NOT NULL,
        VehicleType NVARCHAR(50) NOT NULL DEFAULT 'Motorbike',
        EntryTime DATETIME2 NOT NULL,
        EntryImagePath NVARCHAR(500) NULL,
        PlateImagePath NVARCHAR(500) NULL,
        ExitTime DATETIME2 NULL,
        ExitImagePath NVARCHAR(500) NULL,
        Status INT NOT NULL DEFAULT 1, -- 1: Open, 2: Closed, 3: Alert
        PenaltyAmount DECIMAL(18,2) NOT NULL DEFAULT 0,
        CreatedAt DATETIME2 NOT NULL DEFAULT GETDATE()
    );

    CREATE INDEX IX_Tickets_Plate_Status ON Tickets(Plate, Status);
    CREATE INDEX IX_Tickets_TicketCode ON Tickets(TicketCode);

    PRINT N'Da tao bang Tickets thanh cong!';
END
ELSE
BEGIN
    PRINT N'Bang Tickets da ton tai.';
END
GO

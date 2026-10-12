
/*
    SmartParking - Database Schema
    SQL Server

    Chuc nang:
    1. Tao database SmartParking neu chua ton tai.
    2. Tao bang Tickets neu chua ton tai.
    3. Tao index phuc vu truy van ve xe.

    Ticket Status:
    1 = Open
    2 = Closed
    3 = Alert
*/

-- 1. Tao database neu chua ton tai
IF DB_ID(N'SmartParking') IS NULL
BEGIN
    CREATE DATABASE [SmartParking];
END;
GO

-- 2. Su dung database
USE [SmartParking];
GO

-- 3. Tao bang Tickets neu chua ton tai
IF OBJECT_ID(N'dbo.Tickets', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Tickets
    (
        TicketId BIGINT IDENTITY(1,1) NOT NULL,

        TicketCode NVARCHAR(50) NOT NULL,

        Plate NVARCHAR(30) NOT NULL,

        VehicleType NVARCHAR(50) NOT NULL
            CONSTRAINT DF_Tickets_VehicleType
            DEFAULT (N'Motorbike'),

        EntryTime DATETIME2(3) NOT NULL,

        EntryImagePath NVARCHAR(1000) NULL,

        PlateImagePath NVARCHAR(1000) NULL,

        ExitTime DATETIME2(3) NULL,

        ExitImagePath NVARCHAR(1000) NULL,

        Status INT NOT NULL
            CONSTRAINT DF_Tickets_Status
            DEFAULT (1),

        PenaltyAmount DECIMAL(18,2) NOT NULL
            CONSTRAINT DF_Tickets_PenaltyAmount
            DEFAULT (0),

        CreatedAt DATETIME2(3) NOT NULL
            CONSTRAINT DF_Tickets_CreatedAt
            DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_Tickets
            PRIMARY KEY (TicketId),

        CONSTRAINT UQ_Tickets_TicketCode
            UNIQUE (TicketCode),

        CONSTRAINT CK_Tickets_Status
            CHECK (Status IN (1, 2, 3)),

        CONSTRAINT CK_Tickets_PenaltyAmount
            CHECK (PenaltyAmount >= 0)
    );
END;
GO

-- 4. Index phuc vu tim ve theo bien so va trang thai
IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = N'IX_Tickets_Plate_Status'
      AND object_id = OBJECT_ID(N'dbo.Tickets')
)
BEGIN
    CREATE INDEX IX_Tickets_Plate_Status
        ON dbo.Tickets (Plate, Status);
END;
GO

-- 5. Index phuc vu sap xep ve theo thoi gian tao
IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = N'IX_Tickets_CreatedAt'
      AND object_id = OBJECT_ID(N'dbo.Tickets')
)
BEGIN
    CREATE INDEX IX_Tickets_CreatedAt
        ON dbo.Tickets (CreatedAt);
END;
GO

PRINT N'SmartParking schema script completed.';
GO

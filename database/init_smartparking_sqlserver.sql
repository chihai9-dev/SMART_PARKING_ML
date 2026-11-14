-- =======================================================
-- KHOI TAO DATABASE VA BANG LUU LICH SU NHAN DIEN BIEN SO
-- Chay file nay trong SSMS hoac cong cu SQL Server
-- =======================================================

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

USE SmartParking;
GO

-- Xoa bang Tickets cu neu van con. Du lieu ve cu trong bang nay se bi xoa.
IF OBJECT_ID(N'dbo.Tickets', N'U') IS NOT NULL
BEGIN
    DROP TABLE dbo.Tickets;
    PRINT N'Da xoa bang Tickets cu.';
END
GO

-- Bang PlateScans luu lich su nhan dien bien so xe.
IF OBJECT_ID(N'dbo.PlateScans', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.PlateScans (
        ScanId BIGINT IDENTITY(1,1) PRIMARY KEY,
        Plate NVARCHAR(50) NOT NULL,
        VehicleType NVARCHAR(50) NOT NULL DEFAULT 'Vehicle',
        Confidence FLOAT NOT NULL DEFAULT 1.0,
        ImagePath NVARCHAR(500) NULL,
        CropImagePath NVARCHAR(500) NULL,
        ScanTime DATETIME2 NOT NULL DEFAULT GETDATE(),
        Note NVARCHAR(200) NULL,
        CreatedAt DATETIME2 NOT NULL DEFAULT GETDATE()
    );

    CREATE INDEX IX_PlateScans_Plate ON dbo.PlateScans(Plate);
    CREATE INDEX IX_PlateScans_ScanTime ON dbo.PlateScans(ScanTime);
    PRINT N'Da tao bang PlateScans thanh cong!';
END
ELSE
BEGIN
    PRINT N'Bang PlateScans da ton tai.';
END
GO

-- =======================================================
-- KHOI TAO DATABASE VA BANG LUU LICH SU NHAN DIEN BIEN SO
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

IF OBJECT_ID(N'dbo.PlateScans', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.PlateScans (
        ScanId BIGINT IDENTITY(1,1) PRIMARY KEY,
        Plate NVARCHAR(50) NOT NULL,
        Confidence FLOAT NOT NULL DEFAULT 1.0,
        ImagePath NVARCHAR(500) NULL,
        CropImagePath NVARCHAR(500) NULL,
        PlateColorCode NVARCHAR(20) NULL,
        PlateColorLabel NVARCHAR(100) NULL,
        PlateColorConfidence FLOAT NULL,
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

IF COL_LENGTH(N'dbo.PlateScans', N'PlateColorCode') IS NULL
    ALTER TABLE dbo.PlateScans ADD PlateColorCode NVARCHAR(20) NULL;
IF COL_LENGTH(N'dbo.PlateScans', N'PlateColorLabel') IS NULL
    ALTER TABLE dbo.PlateScans ADD PlateColorLabel NVARCHAR(100) NULL;
IF COL_LENGTH(N'dbo.PlateScans', N'PlateColorConfidence') IS NULL
    ALTER TABLE dbo.PlateScans ADD PlateColorConfidence FLOAT NULL;
GO

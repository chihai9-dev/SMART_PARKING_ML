USE SmartParking;
GO

IF COL_LENGTH(N'dbo.PlateScans', N'PlateColorCode') IS NULL
    ALTER TABLE dbo.PlateScans ADD PlateColorCode NVARCHAR(20) NULL;
IF COL_LENGTH(N'dbo.PlateScans', N'PlateColorLabel') IS NULL
    ALTER TABLE dbo.PlateScans ADD PlateColorLabel NVARCHAR(100) NULL;
IF COL_LENGTH(N'dbo.PlateScans', N'PlateColorConfidence') IS NULL
    ALTER TABLE dbo.PlateScans ADD PlateColorConfidence FLOAT NULL;
GO

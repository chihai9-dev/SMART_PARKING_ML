USE SmartParking;
GO

IF COL_LENGTH(N'dbo.PlateScans', N'PlateColorCode') IS NULL
    ALTER TABLE dbo.PlateScans ADD PlateColorCode NVARCHAR(20) NULL;
IF COL_LENGTH(N'dbo.PlateScans', N'PlateColorLabel') IS NULL
    ALTER TABLE dbo.PlateScans ADD PlateColorLabel NVARCHAR(100) NULL;
IF COL_LENGTH(N'dbo.PlateScans', N'PlateColorConfidence') IS NULL
    ALTER TABLE dbo.PlateScans ADD PlateColorConfidence FLOAT NULL;
IF COL_LENGTH(N'dbo.PlateScans', N'ColorCode') IS NULL
    ALTER TABLE dbo.PlateScans ADD ColorCode NVARCHAR(20) NULL;
GO

UPDATE dbo.PlateScans
SET ColorCode = PlateColorCode
WHERE ColorCode IS NULL
  AND PlateColorCode IS NOT NULL;
GO

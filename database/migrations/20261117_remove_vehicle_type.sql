-- Chay mot lan tren database SmartParking hien co.
USE SmartParking;
GO

IF OBJECT_ID(N'dbo.PlateScans', N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.PlateScans', N'VehicleType') IS NOT NULL
BEGIN
    DECLARE @DefaultConstraintName sysname;

    SELECT @DefaultConstraintName = dc.name
    FROM sys.default_constraints AS dc
    INNER JOIN sys.columns AS col
        ON col.object_id = dc.parent_object_id
       AND col.column_id = dc.parent_column_id
    WHERE dc.parent_object_id = OBJECT_ID(N'dbo.PlateScans')
      AND col.name = N'VehicleType';

    IF @DefaultConstraintName IS NOT NULL
        EXEC(N'ALTER TABLE dbo.PlateScans DROP CONSTRAINT ' + QUOTENAME(@DefaultConstraintName));

    ALTER TABLE dbo.PlateScans DROP COLUMN VehicleType;
    PRINT N'Da xoa cot VehicleType.';
END
ELSE
    PRINT N'Cot VehicleType khong ton tai hoac bang PlateScans chua duoc tao.';
GO

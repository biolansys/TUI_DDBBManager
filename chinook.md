# Database Report

## Summary
- Path: `C:\Varios\IA\TUI\sqlite\chinook.db`
- Size: `46363648` bytes
- Modified: `2026-05-09 15:47:59`
- Tables: `12`
- Views: `0`
- Indexes: `10`
- Triggers: `0`

## Objects

### table: `albums`
- Rows: `347`
- Columns:
  - `AlbumId` (INTEGER)
  - `Title` (NVARCHAR(160))
  - `ArtistId` (INTEGER)
- SQL:
```sql
CREATE TABLE "albums"
(
    [AlbumId] INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    [Title] NVARCHAR(160)  NOT NULL,
    [ArtistId] INTEGER  NOT NULL,
    FOREIGN KEY ([ArtistId]) REFERENCES "artists" ([ArtistId]) 
		ON DELETE NO ACTION ON UPDATE NO ACTION
)
```

### table: `artists`
- Rows: `275`
- Columns:
  - `ArtistId` (INTEGER)
  - `Name` (NVARCHAR(120))
- SQL:
```sql
CREATE TABLE "artists"
(
    [ArtistId] INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    [Name] NVARCHAR(120)
)
```

### table: `customers`
- Rows: `59`
- Columns:
  - `CustomerId` (INTEGER)
  - `FirstName` (NVARCHAR(40))
  - `LastName` (NVARCHAR(20))
  - `Company` (NVARCHAR(80))
  - `Address` (NVARCHAR(70))
  - `City` (NVARCHAR(40))
  - `State` (NVARCHAR(40))
  - `Country` (NVARCHAR(40))
  - `PostalCode` (NVARCHAR(10))
  - `Phone` (NVARCHAR(24))
  - `Fax` (NVARCHAR(24))
  - `Email` (NVARCHAR(60))
  - `SupportRepId` (INTEGER)
- SQL:
```sql
CREATE TABLE "customers"
(
    [CustomerId] INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    [FirstName] NVARCHAR(40)  NOT NULL,
    [LastName] NVARCHAR(20)  NOT NULL,
    [Company] NVARCHAR(80),
    [Address] NVARCHAR(70),
    [City] NVARCHAR(40),
    [State] NVARCHAR(40),
    [Country] NVARCHAR(40),
    [PostalCode] NVARCHAR(10),
    [Phone] NVARCHAR(24),
    [Fax] NVARCHAR(24),
    [Email] NVARCHAR(60)  NOT NULL,
    [SupportRepId] INTEGER,
    FOREIGN KEY ([SupportRepId]) REFERENCES "employees" ([EmployeeId]) 
		ON DELETE NO ACTION ON UPDATE NO ACTION
)
```

### table: `employees`
- Rows: `8`
- Columns:
  - `EmployeeId` (INTEGER)
  - `LastName` (NVARCHAR(20))
  - `FirstName` (NVARCHAR(20))
  - `Title` (NVARCHAR(30))
  - `ReportsTo` (INTEGER)
  - `BirthDate` (DATETIME)
  - `HireDate` (DATETIME)
  - `Address` (NVARCHAR(70))
  - `City` (NVARCHAR(40))
  - `State` (NVARCHAR(40))
  - `Country` (NVARCHAR(40))
  - `PostalCode` (NVARCHAR(10))
  - `Phone` (NVARCHAR(24))
  - `Fax` (NVARCHAR(24))
  - `Email` (NVARCHAR(60))
- SQL:
```sql
CREATE TABLE "employees"
(
    [EmployeeId] INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    [LastName] NVARCHAR(20)  NOT NULL,
    [FirstName] NVARCHAR(20)  NOT NULL,
    [Title] NVARCHAR(30),
    [ReportsTo] INTEGER,
    [BirthDate] DATETIME,
    [HireDate] DATETIME,
    [Address] NVARCHAR(70),
    [City] NVARCHAR(40),
    [State] NVARCHAR(40),
    [Country] NVARCHAR(40),
    [PostalCode] NVARCHAR(10),
    [Phone] NVARCHAR(24),
    [Fax] NVARCHAR(24),
    [Email] NVARCHAR(60),
    FOREIGN KEY ([ReportsTo]) REFERENCES "employees" ([EmployeeId]) 
		ON DELETE NO ACTION ON UPDATE NO ACTION
)
```

### table: `fights`
- Rows: `1000000`
- Columns:
  - `FL_DATE` (TEXT)
  - `DEP_DELAY` (INTEGER)
  - `ARR_DELAY` (INTEGER)
  - `AIR_TIME` (INTEGER)
  - `DISTANCE` (INTEGER)
  - `DEP_TIME` (TEXT)
  - `ARR_TIME` (TEXT)
- SQL:
```sql
CREATE TABLE "fights" ("FL_DATE" TEXT,"DEP_DELAY" INTEGER,"ARR_DELAY" INTEGER,"AIR_TIME" INTEGER,"DISTANCE" INTEGER,"DEP_TIME" TEXT,"ARR_TIME" TEXT)
```

### table: `genres`
- Rows: `25`
- Columns:
  - `GenreId` (INTEGER)
  - `Name` (NVARCHAR(120))
- SQL:
```sql
CREATE TABLE "genres"
(
    [GenreId] INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    [Name] NVARCHAR(120)
)
```

### table: `invoice_items`
- Rows: `2240`
- Columns:
  - `InvoiceLineId` (INTEGER)
  - `InvoiceId` (INTEGER)
  - `TrackId` (INTEGER)
  - `UnitPrice` (NUMERIC(10,2))
  - `Quantity` (INTEGER)
- SQL:
```sql
CREATE TABLE "invoice_items"
(
    [InvoiceLineId] INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    [InvoiceId] INTEGER  NOT NULL,
    [TrackId] INTEGER  NOT NULL,
    [UnitPrice] NUMERIC(10,2)  NOT NULL,
    [Quantity] INTEGER  NOT NULL,
    FOREIGN KEY ([InvoiceId]) REFERENCES "invoices" ([InvoiceId]) 
		ON DELETE NO ACTION ON UPDATE NO ACTION,
    FOREIGN KEY ([TrackId]) REFERENCES "tracks" ([TrackId]) 
		ON DELETE NO ACTION ON UPDATE NO ACTION
)
```

### table: `invoices`
- Rows: `412`
- Columns:
  - `InvoiceId` (INTEGER)
  - `CustomerId` (INTEGER)
  - `InvoiceDate` (DATETIME)
  - `BillingAddress` (NVARCHAR(70))
  - `BillingCity` (NVARCHAR(40))
  - `BillingState` (NVARCHAR(40))
  - `BillingCountry` (NVARCHAR(40))
  - `BillingPostalCode` (NVARCHAR(10))
  - `Total` (NUMERIC(10,2))
- SQL:
```sql
CREATE TABLE "invoices"
(
    [InvoiceId] INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    [CustomerId] INTEGER  NOT NULL,
    [InvoiceDate] DATETIME  NOT NULL,
    [BillingAddress] NVARCHAR(70),
    [BillingCity] NVARCHAR(40),
    [BillingState] NVARCHAR(40),
    [BillingCountry] NVARCHAR(40),
    [BillingPostalCode] NVARCHAR(10),
    [Total] NUMERIC(10,2)  NOT NULL,
    FOREIGN KEY ([CustomerId]) REFERENCES "customers" ([CustomerId]) 
		ON DELETE NO ACTION ON UPDATE NO ACTION
)
```

### table: `media_types`
- Rows: `5`
- Columns:
  - `MediaTypeId` (INTEGER)
  - `Name` (NVARCHAR(120))
- SQL:
```sql
CREATE TABLE "media_types"
(
    [MediaTypeId] INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    [Name] NVARCHAR(120)
)
```

### table: `playlist_track`
- Rows: `8715`
- Columns:
  - `PlaylistId` (INTEGER)
  - `TrackId` (INTEGER)
- SQL:
```sql
CREATE TABLE "playlist_track"
(
    [PlaylistId] INTEGER  NOT NULL,
    [TrackId] INTEGER  NOT NULL,
    CONSTRAINT [PK_PlaylistTrack] PRIMARY KEY  ([PlaylistId], [TrackId]),
    FOREIGN KEY ([PlaylistId]) REFERENCES "playlists" ([PlaylistId]) 
		ON DELETE NO ACTION ON UPDATE NO ACTION,
    FOREIGN KEY ([TrackId]) REFERENCES "tracks" ([TrackId]) 
		ON DELETE NO ACTION ON UPDATE NO ACTION
)
```

### table: `playlists`
- Rows: `18`
- Columns:
  - `PlaylistId` (INTEGER)
  - `Name` (NVARCHAR(120))
- SQL:
```sql
CREATE TABLE "playlists"
(
    [PlaylistId] INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    [Name] NVARCHAR(120)
)
```

### table: `tracks`
- Rows: `3503`
- Columns:
  - `TrackId` (INTEGER)
  - `Name` (NVARCHAR(200))
  - `AlbumId` (INTEGER)
  - `MediaTypeId` (INTEGER)
  - `GenreId` (INTEGER)
  - `Composer` (NVARCHAR(220))
  - `Milliseconds` (INTEGER)
  - `Bytes` (INTEGER)
  - `UnitPrice` (NUMERIC(10,2))
- SQL:
```sql
CREATE TABLE "tracks"
(
    [TrackId] INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    [Name] NVARCHAR(200)  NOT NULL,
    [AlbumId] INTEGER,
    [MediaTypeId] INTEGER  NOT NULL,
    [GenreId] INTEGER,
    [Composer] NVARCHAR(220),
    [Milliseconds] INTEGER  NOT NULL,
    [Bytes] INTEGER,
    [UnitPrice] NUMERIC(10,2)  NOT NULL,
    FOREIGN KEY ([AlbumId]) REFERENCES "albums" ([AlbumId]) 
		ON DELETE NO ACTION ON UPDATE NO ACTION,
    FOREIGN KEY ([GenreId]) REFERENCES "genres" ([GenreId]) 
		ON DELETE NO ACTION ON UPDATE NO ACTION,
    FOREIGN KEY ([MediaTypeId]) REFERENCES "media_types" ([MediaTypeId]) 
		ON DELETE NO ACTION ON UPDATE NO ACTION
)
```

### index: `IFK_AlbumArtistId`
- SQL:
```sql
CREATE INDEX [IFK_AlbumArtistId] ON "albums" ([ArtistId])
```

### index: `IFK_CustomerSupportRepId`
- SQL:
```sql
CREATE INDEX [IFK_CustomerSupportRepId] ON "customers" ([SupportRepId])
```

### index: `IFK_EmployeeReportsTo`
- SQL:
```sql
CREATE INDEX [IFK_EmployeeReportsTo] ON "employees" ([ReportsTo])
```

### index: `IFK_InvoiceCustomerId`
- SQL:
```sql
CREATE INDEX [IFK_InvoiceCustomerId] ON "invoices" ([CustomerId])
```

### index: `IFK_InvoiceLineInvoiceId`
- SQL:
```sql
CREATE INDEX [IFK_InvoiceLineInvoiceId] ON "invoice_items" ([InvoiceId])
```

### index: `IFK_InvoiceLineTrackId`
- SQL:
```sql
CREATE INDEX [IFK_InvoiceLineTrackId] ON "invoice_items" ([TrackId])
```

### index: `IFK_PlaylistTrackTrackId`
- SQL:
```sql
CREATE INDEX [IFK_PlaylistTrackTrackId] ON "playlist_track" ([TrackId])
```

### index: `IFK_TrackAlbumId`
- SQL:
```sql
CREATE INDEX [IFK_TrackAlbumId] ON "tracks" ([AlbumId])
```

### index: `IFK_TrackGenreId`
- SQL:
```sql
CREATE INDEX [IFK_TrackGenreId] ON "tracks" ([GenreId])
```

### index: `IFK_TrackMediaTypeId`
- SQL:
```sql
CREATE INDEX [IFK_TrackMediaTypeId] ON "tracks" ([MediaTypeId])
```

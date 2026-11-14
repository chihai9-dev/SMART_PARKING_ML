using SmartParking.Application.Interfaces;
using SmartParking.Application.Services;
using SmartParking.Infrastructure.Data;
using SmartParking.Infrastructure.Repositories;

var builder = WebApplication.CreateBuilder(args);

// Controllers
builder.Services.AddControllers();

// Swagger: API nhận diện biển số không yêu cầu đăng nhập.
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// Database
builder.Services.AddSingleton<DbConnectionFactory>();

// Repository: lưu và truy vấn lịch sử nhận diện biển số.
builder.Services.AddScoped<
    IPlateScanRepository,
    PlateScanRepository>();

// Service: nghiệp vụ lịch sử nhận diện biển số.
builder.Services.AddScoped<
    IPlateScanService,
    PlateScanService>();

var app = builder.Build();

// Swagger
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

// Không cấu hình JWT Authentication/Authorization.
app.UseHttpsRedirection();

app.MapControllers();

app.Run();

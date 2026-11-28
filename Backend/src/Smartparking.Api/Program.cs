using SmartParking.Application.Interfaces;
using SmartParking.Application.Services;
using SmartParking.Infrastructure.Data;
using SmartParking.Infrastructure.Repositories;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddHttpClient("PythonApi", client =>
{
    var pythonApiUrl = builder.Configuration["PythonApi:BaseUrl"] ?? "http://127.0.0.1:5000";
    client.BaseAddress = new Uri(pythonApiUrl.TrimEnd('/') + "/");
    client.Timeout = TimeSpan.FromMinutes(3);
});

builder.Services.AddSingleton<DbConnectionFactory>();
builder.Services.AddScoped<IPlateScanRepository, PlateScanRepository>();
builder.Services.AddScoped<IPlateScanService, PlateScanService>();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI(options =>
    {
        options.SwaggerEndpoint("/swagger/v1/swagger.json", "SmartParking Backend (.NET)");
        options.SwaggerEndpoint(
            "/python-api/openapi.json",
            "SmartParking Python AI Service");
    });
}

app.UseHttpsRedirection();
app.MapControllers();

app.Run();

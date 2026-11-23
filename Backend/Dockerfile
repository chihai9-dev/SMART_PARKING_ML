FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

# Build context is the repository root.
COPY Backend/ ./
RUN dotnet restore "src/Smartparking.Api/Smartparking.Api.csproj"
RUN dotnet publish "src/Smartparking.Api/Smartparking.Api.csproj" \
    --configuration Release \
    --no-restore \
    --output /app/publish \
    /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish ./

ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

ENTRYPOINT ["dotnet", "Smartparking.Api.dll"]

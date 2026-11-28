using System.Text.Json.Nodes;
using Microsoft.AspNetCore.Mvc;

namespace SmartParking.Api.Controllers;

[ApiController]
[ApiExplorerSettings(IgnoreApi = true)]
[Route("python-api")]
public sealed class PythonApiProxyController : ControllerBase
{
    private readonly HttpClient _pythonApi;

    public PythonApiProxyController(IHttpClientFactory httpClientFactory)
    {
        _pythonApi = httpClientFactory.CreateClient("PythonApi");
    }

    [HttpGet("openapi.json")]
    public async Task<IActionResult> GetOpenApi(CancellationToken cancellationToken)
    {
        try
        {
            using var response = await _pythonApi.GetAsync("openapi.json", cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return StatusCode((int)response.StatusCode);
            }

            var document = JsonNode.Parse(
                await response.Content.ReadAsStringAsync(cancellationToken));
            if (document is not JsonObject openApiObject)
            {
                return Problem(
                    title: "Python API returned an invalid OpenAPI document.",
                    statusCode: StatusCodes.Status502BadGateway);
            }

            openApiObject["servers"] = new JsonArray(
                new JsonObject { ["url"] = "/python-api" });

            return Content(openApiObject.ToJsonString(), "application/json");
        }
        catch (HttpRequestException exception)
        {
            return Problem(
                title: "Unable to load the Python API OpenAPI document.",
                detail: exception.Message,
                statusCode: StatusCodes.Status503ServiceUnavailable);
        }
    }

    [HttpGet("api/model-info")]
    public Task<IActionResult> GetModelInfo(CancellationToken cancellationToken) =>
        ForwardAsync(HttpMethod.Get, "api/model-info", cancellationToken);

    [HttpGet("api/scans")]
    public Task<IActionResult> GetScans(CancellationToken cancellationToken) =>
        ForwardAsync(HttpMethod.Get, "api/scans", cancellationToken);

    [HttpGet("scan-image/{filename}")]
    public Task<IActionResult> GetScanImage(
        string filename,
        CancellationToken cancellationToken) =>
        ForwardAsync(
            HttpMethod.Get,
            "scan-image/" + Uri.EscapeDataString(filename),
            cancellationToken);

    [HttpPost("api/preview-plate")]
    public Task<IActionResult> PreviewPlate(CancellationToken cancellationToken) =>
        ForwardImageAsync("api/preview-plate", cancellationToken);

    [HttpPost("api/scan-plate")]
    public Task<IActionResult> ScanPlate(CancellationToken cancellationToken) =>
        ForwardImageAsync("api/scan-plate", cancellationToken);

    [HttpPost("api/classify-plate-color")]
    public Task<IActionResult> ClassifyPlateColor(CancellationToken cancellationToken) =>
        ForwardImageAsync("api/classify-plate-color", cancellationToken);

    private Task<IActionResult> ForwardImageAsync(
        string path,
        CancellationToken cancellationToken)
    {
        var target = path + Request.QueryString;
        var request = new HttpRequestMessage(HttpMethod.Post, target)
        {
            Content = new StreamContent(Request.Body),
        };
        if (Request.ContentType is not null)
        {
            request.Content.Headers.TryAddWithoutValidation(
                "Content-Type",
                Request.ContentType);
        }

        return SendAsync(request, cancellationToken);
    }

    private Task<IActionResult> ForwardAsync(
        HttpMethod method,
        string path,
        CancellationToken cancellationToken)
    {
        var request = new HttpRequestMessage(
            method,
            path + Request.QueryString);
        return SendAsync(request, cancellationToken);
    }

    private async Task<IActionResult> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        using (request)
        {
            try
            {
                using var response = await _pythonApi.SendAsync(
                    request,
                    HttpCompletionOption.ResponseHeadersRead,
                    cancellationToken);
                var body = await response.Content.ReadAsByteArrayAsync(cancellationToken);
                var contentType = response.Content.Headers.ContentType?.ToString()
                    ?? "application/octet-stream";

                Response.StatusCode = (int)response.StatusCode;
                return File(body, contentType);
            }
            catch (HttpRequestException exception)
            {
                return Problem(
                    title: "Unable to reach the Python AI service.",
                    detail: exception.Message,
                    statusCode: StatusCodes.Status503ServiceUnavailable);
            }
        }
    }
}

using Microsoft.AspNetCore.Mvc;
using SmartParking.Application.DTOs.PlateScans;
using SmartParking.Application.Interfaces;

namespace SmartParking.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class PlateScansController : ControllerBase
{
    private readonly IPlateScanService _service;

    public PlateScansController(IPlateScanService service)
    {
        _service = service;
    }

    [HttpGet]
    public async Task<IActionResult> GetAll([FromQuery] string? search)
    {
        var list = await _service.GetAllAsync(search);
        return Ok(list);
    }

    [HttpGet("stats")]
    public async Task<IActionResult> GetStats()
    {
        var stats = await _service.GetStatsAsync();
        return Ok(stats);
    }

    [HttpGet("{id:long}")]
    public async Task<IActionResult> GetById(long id)
    {
        var scan = await _service.GetByIdAsync(id);
        if (scan == null)
        {
            return NotFound(new { message = "Không tìm thấy lượt nhận diện." });
        }
        return Ok(scan);
    }

    [HttpPost]
    public async Task<IActionResult> Create([FromBody] CreatePlateScanRequest request)
    {
        try
        {
            var created = await _service.CreateAsync(request);
            return CreatedAtAction(nameof(GetById), new { id = created.ScanId }, created);
        }
        catch (ArgumentException ex)
        {
            return BadRequest(new { message = ex.Message });
        }
    }

    [HttpDelete("{id:long}")]
    public async Task<IActionResult> Delete(long id)
    {
        var deleted = await _service.DeleteAsync(id);
        if (!deleted)
        {
            return NotFound(new { message = "Không tìm thấy bản ghi để xóa." });
        }
        return Ok(new { message = "Xóa bản ghi thành công." });
    }
}

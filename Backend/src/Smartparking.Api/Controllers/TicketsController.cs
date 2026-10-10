using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using SmartParking.Application.DTOs.Tickets;
using SmartParking.Application.Interfaces;

namespace SmartParking.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class TicketsController : ControllerBase
{
    private readonly ITicketService _service;

    public TicketsController(ITicketService service)
    {
        _service = service;
    }

    [HttpGet]
    public async Task<IActionResult> GetAll()
    {
        var tickets = await _service.GetAllAsync();

        return Ok(tickets);
    }

    [HttpGet("{id:long}")]
    public async Task<IActionResult> GetById(long id)
    {
        var ticket = await _service.GetByIdAsync(id);

        if (ticket == null)
        {
            return NotFound(new
            {
                message = "Không tìm thấy vé."
            });
        }

        return Ok(ticket);
    }

    [HttpGet("open/{plate}")]
    public async Task<IActionResult> GetOpenByPlate(
        string plate)
    {
        var ticket =
            await _service.GetOpenByPlateAsync(plate);

        if (ticket == null)
        {
            return NotFound(new
            {
                message = "Không tìm thấy vé đang gửi."
            });
        }

        return Ok(ticket);
    }

    [HttpPost("entry")]
    public async Task<IActionResult> CreateEntry(
        [FromBody] CreateTicketRequest request)
    {
        try
        {
            var ticket =
                await _service.CreateEntryAsync(request);

            return CreatedAtAction(
                nameof(GetById),
                new { id = ticket.TicketId },
                ticket);
        }
        catch (ArgumentException ex)
        {
            return BadRequest(new
            {
                message = ex.Message
            });
        }
        catch (InvalidOperationException ex)
        {
            return Conflict(new
            {
                message = ex.Message
            });
        }
    }

    [HttpPost("{id:long}/exit")]
    public async Task<IActionResult> CloseExit(
        long id,
        [FromBody] ExitTicketRequest request)
    {
        if (request.Status != 2 &&
            request.Status != 3)
        {
            return BadRequest(new
            {
                message =
                    "Status phải là 2 (Closed) hoặc 3 (Alert)."
            });
        }

        var ticket =
            await _service.CloseExitAsync(
                id,
                request.ExitImagePath,
                request.PenaltyAmount,
                request.Status);

        if (ticket == null)
        {
            return NotFound(new
            {
                message =
                    "Không tìm thấy vé đang gửi."
            });
        }

        return Ok(ticket);
    }
}

public class ExitTicketRequest
{
    public string? ExitImagePath { get; set; }

    public decimal PenaltyAmount { get; set; }

    public int Status { get; set; } = 2;
}
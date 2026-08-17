from bell_mcp_platform import mcp


@mcp.tool()
async def fizzbuzz(x: int) -> dict:
    """Return Fizz, Buzz, or FizzBuzz for numbers from 1 to x."""
    result = {}
    for n in range(1, x + 1):
        if n % 15 == 0:
            result[n] = "FizzBuzz"
        elif n % 5 == 0:
            result[n] = "Buzz"
        elif n % 3 == 0:
            result[n] = "Fizz"
    return result

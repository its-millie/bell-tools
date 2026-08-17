# FizzBuzz Generator

## Purpose

Generates FizzBuzz results for a continuous range of integers from 1 to a specified upper limit. This is a classic programming challenge that demonstrates divisibility logic and conditional branching.

**Use this tool when you need to:**
- Generate FizzBuzz sequences for educational or testing purposes
- Demonstrate basic divisibility rules to users
- Create sample data for algorithm testing
- Verify number theory concepts in a simple, visual way

## Algorithm

The tool applies the following rules to each number `n` in the range [1, x]:

1. **FizzBuzz** (divisible by both 3 and 5 → divisible by 15)
2. **Fizz** (divisible by 5 only)  
3. **Buzz** (divisible by 3 only)
4. Numbers not matching any rule are **omitted** from results

## Parameters

### `x` (integer, required)
- **Type**: `int`
- **Required**: Yes
- **Description**: The upper limit of the number range (inclusive)
- **Valid Range**: 1 to 100,000 (recommended for performance)
- **Behavior**: Generates results for all integers from 1 through x

**Examples:**
- `x=15` → processes numbers 1, 2, 3, ..., 15
- `x=5` → processes numbers 1, 2, 3, 4, 5
- `x=0` → returns empty dict (no numbers to process)

## Returns

**Type**: `dict[int, str]`

Returns a dictionary mapping integers to their FizzBuzz string values.

### Structure:
```python
{
    3: "Buzz",      # Divisible by 3
    5: "Fizz",      # Divisible by 5
    6: "Buzz",      # Divisible by 3
    10: "Fizz",     # Divisible by 5
    15: "FizzBuzz", # Divisible by both 3 and 5
    ...
}

Important Notes:
Only numbers that match FizzBuzz rules appear in the result
Numbers divisible by neither 3 nor 5 are excluded
Keys are integers, values are strings
Results are ordered sequentially (Python 3.7+ dict ordering)
Usage Examples
Example 1: Basic Usage (Small Range)
Example 2: Extended Range
Example 3: Edge Case - Zero
Example 4: Edge Case - Single Number
Example 5: Finding All FizzBuzz Numbers
Performance Characteristics
Time Complexity: O(n) where n = x
Space Complexity: O(k) where k = count of numbers divisible by 3 or 5
Typical Result Size: ~47% of input range (approximately 1/3 + 1/5 - 1/15 of numbers)
Approximate Output Sizes:
x=100 → ~47 entries
x=1000 → ~467 entries
x=10000 → ~4667 entries
Common Use Cases
1. Educational Demonstrations
2. Testing Divisibility Understanding
3. Algorithm Validation
Edge Cases & Behavior
Input	Result	Explanation
x=0	{}	No numbers in range [1, 0]
x=1	{}	1 is not divisible by 3 or 5
x=3	{3: "Buzz"}	First Buzz number
x=5	{3: "Buzz", 5: "Fizz"}	First Fizz number included
x=15	Includes {15: "FizzBuzz"}	First FizzBuzz number
x=-5	{}	Range [1, -5] is empty
Implementation Notes
Uses modulo operator (%) for divisibility checks
Checks divisibility by 15 first (optimization: avoids redundant 3 and 5 checks)
Returns empty dict rather than None for zero cases
Does not validate maximum input size (caller responsibility)
Error Handling
This tool does not raise exceptions for:

Negative values (returns empty dict)
Zero values (returns empty dict)
Very large values (may impact performance)
Related Patterns
This tool demonstrates:

Modulo arithmetic for divisibility testing
Conditional branching based on multiple criteria
Dictionary comprehension patterns (internal implementation)
Number theory basics (least common multiples)
When NOT to Use
Don't use for non-integer inputs (will raise TypeError)
Don't use for extremely large ranges (x > 1,000,000) without considering performance
Don't use if you need the full sequence including non-matching numbers
Don't use if you need custom divisibility rules (this tool uses fixed 3/5/15 rules)
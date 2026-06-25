param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Args
)

python scripts/smoke_test.py @Args
exit $LASTEXITCODE


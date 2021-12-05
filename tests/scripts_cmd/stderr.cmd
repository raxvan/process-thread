
:: https://stackoverflow.com/questions/357315/how-to-get-list-of-arguments

@echo off
echo Writing to stderr...
for %%I IN (%*) DO echo %%I 1>&2





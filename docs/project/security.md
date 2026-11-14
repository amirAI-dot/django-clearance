# Security

django-clearance decides who reaches what. A way round it - a row shown to
somebody it should not reach, a field read without its permission, somebody
giving themselves access - is a security problem, and is treated as one.

## Reporting one

**Report it privately, not in a public issue.** On GitHub, open the
repository's *Security* tab and choose *Report a vulnerability*. The report
is seen only by the maintainers until a fix is out.

Say what you can of:

* what a person can do that they should not - and who that person is: signed
  in, holding what;
* the steps, or a test that shows it;
* the versions of the library, Django, Python and - if it is involved - DRF.

## What happens next

The problem is reproduced and fixed in a release, with a test that holds it,
and the changelog says what was fixed.

## Supported versions

Fixes go into the latest release. The library is young - alpha, `0.x` - so
upgrading to the latest release is the way to receive one.

## Already held

The safety rules, the denied-by-default behaviour and the checks of each door
are held by the library's own tests - every way round that a review found has
a test named after it. The [design](../design.md) lists what each rule
protects against.

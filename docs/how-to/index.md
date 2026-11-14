# How-to guides

Each guide answers one question a project meets, in the fewest steps that
answer it. The [tutorial](../tutorial/index.md) builds a project from the
start; these are for a project already under way.

| guide | the question |
|---|---|
| [Adopt it in an existing project](adopt.md) | we use Django's permissions already - what changes? |
| [Scope rows by a field of the person](scope-by-the-person.md) | each person sees their region's rows |
| [An approval only some may give](approval.md) | only a manager approves, and never their own |
| [Reference data everybody reads](reference-data.md) | everybody chooses a branch, few change one |
| [A view that holds no model](view-without-a-model.md) | a report, an export, an API root |
| [Use an admin site of your own](own-admin-site.md) | our admin site has its own header and pages |
| [Keep roles on the user model](roles-on-the-user.md) | our users have a `role` column already |
| [Keep an audit trail](audit-trail.md) | who gave whom what, and when |
| [Check access in CI](ci.md) | the database and the `ACCESS` file must agree |
| [Workers and websockets](long-lived-processes.md) | a process that outlives a request |
| [Test what people may do](testing.md) | a test per rule, not per view |

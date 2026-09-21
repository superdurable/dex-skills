# Custom UI workflow

Use this only after the user chooses a custom frontend.

## Interaction design

Agree on:

- role-specific entry points and navigation;
- list, detail, create, action, and completion experiences;
- which state is canonical and how stale state is refreshed;
- action eligibility and confirmation;
- required inputs, validation, empty states, loading, recoverable errors, and terminal errors;
- responsive behavior and accessibility;
- which Dex Web v2 surfaces remain available to maintainers.

Do not claim application-level UI controls provide platform RBAC. Keep credentials and provider secrets server-side.

## Mock checkpoint

Implement the first pass in the template React TypeScript application using local typed fixtures. Keep network calls out of the mock path. Cover at least the primary happy path plus empty, loading, validation, and provider-error states.

Run the frontend tests and production build. Render or open the mock when the environment supports visual inspection. Summarize the observed interactions and wait for explicit user approval.

Before approval, do not:

- finalize OpenAPI;
- bind components to live endpoints;
- add Dex Client access to the browser;
- implement backend behavior inferred only from the mock.

After approval, make OpenAPI the HTTP contract source and regenerate both server and browser clients. Browsers call the application API or typed Flow RPC boundary, never raw Dex primitives.

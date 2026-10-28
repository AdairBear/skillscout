# Test fixtures

Everything under `malicious/` is deliberately hostile **inert text** for the static scanner tests.
Nothing here is ever executed, by the tests or by skillscout. Hidden-Unicode and fake-secret cases
are generated at test time so this repo's own secret scan stays clean.

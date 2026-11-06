"""
Transport-agnostic descriptions of every Egnyte API call.

Each function here builds an `Operation`: the HTTP method, the path under
`/pubapi`, the query, the body, and the parser that turns the response into the
result. Nothing in this package performs I/O, which is what lets `EgnyteClient`
and `AsyncEgnyteClient` share it rather than each carrying its own copy of the
wire details.

Internal to the package; the public surface is the clients.
"""

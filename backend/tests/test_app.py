from httpx import AsyncClient


def _error(body: dict[str, object]) -> dict[str, object]:
    assert set(body) == {"error"}
    error = body["error"]
    assert isinstance(error, dict)
    assert set(error) == {"code", "message", "details"}
    return error


async def test_openapi_docs_are_served(client: AsyncClient) -> None:
    docs = await client.get("/docs")
    schema = await client.get("/openapi.json")

    assert docs.status_code == 200
    assert schema.status_code == 200
    assert schema.json()["info"]["title"] == "ReleaseGuard API"
    assert "ErrorResponse" in schema.json()["components"]["schemas"]


async def test_openapi_documents_the_real_validation_error_shape(client: AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/api/v1/_test/validate"]["post"]["responses"]
    ref = responses["422"]["content"]["application/json"]["schema"]["$ref"]
    assert ref == "#/components/schemas/ErrorResponse"
    assert "HTTPValidationError" not in schema["components"]["schemas"]


async def test_unknown_route_returns_error_shape(client: AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert _error(response.json())["code"] == "not_found"


async def test_wrong_method_returns_error_shape(client: AsyncClient) -> None:
    response = await client.post("/api/v1/_test/boom", headers={"Origin": "http://testserver"})

    assert response.status_code == 405
    assert _error(response.json())["code"] == "method_not_allowed"
    assert "allow" in response.headers


async def test_validation_error_lists_fields_without_echoing_input(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/_test/validate",
        json={"name": "s3cret-value", "count": "not-a-number"},
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 422
    error = _error(response.json())
    assert error["code"] == "validation_error"
    details = error["details"]
    assert isinstance(details, dict)
    assert details["errors"] == [
        {"loc": ["body", "count"], "msg": details["errors"][0]["msg"], "type": "int_parsing"}
    ]
    assert "not-a-number" not in response.text
    assert "s3cret-value" not in response.text


async def test_app_errors_map_to_status_and_code(client: AsyncClient) -> None:
    not_found = await client.get("/api/v1/_test/errors/not_found")
    forbidden = await client.get("/api/v1/_test/errors/forbidden")
    conflict = await client.get("/api/v1/_test/errors/conflict")

    assert not_found.status_code == 404
    assert _error(not_found.json()) == {
        "code": "not_found",
        "message": "Resource not found.",
        "details": {},
    }
    assert forbidden.status_code == 403
    assert _error(forbidden.json())["message"] == "Only admins can do this."
    assert conflict.status_code == 409
    assert _error(conflict.json()) == {
        "code": "environment_busy",
        "message": "The request conflicts with the current state.",
        "details": {"environment": "prod"},
    }


async def test_unhandled_error_returns_generic_500(client: AsyncClient) -> None:
    response = await client.get("/api/v1/_test/boom")

    assert response.status_code == 500
    assert _error(response.json()) == {
        "code": "internal_error",
        "message": "An unexpected error occurred.",
        "details": {},
    }
    assert "hunter2" not in response.text

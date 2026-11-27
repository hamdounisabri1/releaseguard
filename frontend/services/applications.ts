import { queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/services/api";
import type { components } from "@/types/api";

export type Application = components["schemas"]["ApplicationOut"];
export type ApplicationCreate = components["schemas"]["ApplicationCreate"];
export type ApplicationPage = components["schemas"]["Page_ApplicationOut_"];
export type Environment = components["schemas"]["EnvironmentOut"];

/** The backend's largest page. Search filters this page in the browser (the API has no search). */
const LIST_PAGE_SIZE = 100;

export const applicationsQueryKey = ["applications"] as const;

/** Applications in the workspace; archived ones too when `includeArchived`. */
export function fetchApplications(includeArchived: boolean): Promise<ApplicationPage> {
  return unwrap(
    api.GET("/api/v1/applications", {
      params: { query: { include_archived: includeArchived, page_size: LIST_PAGE_SIZE } },
    }),
  );
}

export function applicationsQueryOptions(includeArchived: boolean) {
  return queryOptions({
    queryKey: [...applicationsQueryKey, "list", { includeArchived }],
    queryFn: () => fetchApplications(includeArchived),
  });
}

/** One application (archived ones too); 404 for an unknown id or another workspace's. */
export function fetchApplication(applicationId: string): Promise<Application> {
  return unwrap(
    api.GET("/api/v1/applications/{application_id}", {
      params: { path: { application_id: applicationId } },
    }),
  );
}

export function applicationQueryOptions(applicationId: string) {
  return queryOptions({
    queryKey: [...applicationsQueryKey, "detail", applicationId],
    queryFn: () => fetchApplication(applicationId),
  });
}

/** The application's environments (development, staging, production). */
export function fetchApplicationEnvironments(applicationId: string): Promise<Environment[]> {
  return unwrap(
    api.GET("/api/v1/applications/{application_id}/environments", {
      params: { path: { application_id: applicationId } },
    }),
  );
}

export function applicationEnvironmentsQueryOptions(applicationId: string) {
  return queryOptions({
    queryKey: [...applicationsQueryKey, "detail", applicationId, "environments"],
    queryFn: () => fetchApplicationEnvironments(applicationId),
  });
}

/**
 * Creates an application and its three environments (Admin, Developer). Fails with 403 for
 * other roles, 409 `repository_already_registered` or 422 `validation_error`.
 */
export function createApplication(body: ApplicationCreate): Promise<Application> {
  return unwrap(api.POST("/api/v1/applications", { body }));
}

/** Archives an application (Admin, Developer). Fails with 403 for other roles, or 409. */
export function archiveApplication(applicationId: string): Promise<Application> {
  return unwrap(
    api.POST("/api/v1/applications/{application_id}/archive", {
      params: { path: { application_id: applicationId } },
    }),
  );
}

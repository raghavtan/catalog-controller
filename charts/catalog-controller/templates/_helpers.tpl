{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "catalog-controller.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "catalog-controller.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "catalog-controller.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" | default "catalog"}}
{{- end }}

{{/*
Common labels
*/}}
{{- define "catalog-controller.labels" -}}
helm.sh/chart: {{ include "catalog-controller.chart" . }}
{{ include "catalog-controller.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "catalog-controller.selectorLabels" -}}
app.kubernetes.io/name: {{ include "catalog-controller.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "catalog-controller.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "catalog-controller.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Get the secret name
*/}}
{{- define "catalog-controller.secretName" -}}
{{- if .Values.compass.credentials.existingSecret }}
{{- .Values.compass.credentials.existingSecret }}
{{- else }}
{{- printf "%s-compass-credentials" (include "catalog-controller.fullname" .) }}
{{- end }}
{{- end }}
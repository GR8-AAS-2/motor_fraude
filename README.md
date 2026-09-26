# Motor de Fraude

Servicio Flask **independiente** de `poliza_seguridad` (código y despliegue
propios), que calcula y valida un hash de integridad sobre los datos de una
póliza. Usa el mismo proyecto de Supabase que `poliza_seguridad`, pero en su
**propia tabla** (`poliza_hashes`). Para el fallback de validación, consulta
por HTTP el servicio de auditoría `poliza_seguridad`.

## Campos que componen el hash

`numero_poliza`, `tipo_documento`, `documento_identidad`, `ramo`,
`tipo_cobertura`, `monto_asegurado`, `fecha_inicio_vigencia`,
`fecha_fin_vigencia`.

El hash es **SHA-256** sobre estos 8 campos concatenados en orden fijo,
normalizando:
- `monto_asegurado` → `Decimal` con 2 decimales fijos (`500000` y
  `"500000.00"` producen el mismo valor).
- Fechas → `YYYY-MM-DD` (se ignora la hora si viene incluida).
- El resto → `str().strip()`.

Esto garantiza que el mismo dato produzca siempre el mismo hash, venga de
una petición directa o del `detalle` (JSON) de un log de auditoría.

## Modelo de datos

Tabla `poliza_hashes` (ver [`sql/schema.sql`](sql/schema.sql)):

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `uuid` (PK) | Autogenerado. |
| `numero_poliza` | `text`, único | Clave de búsqueda del hash. |
| `hash` | `text` | SHA-256 canónico. |
| `fecha_creacion` | `timestamptz` | Default `now()`. |

## Endpoints

Todos (excepto `/api/health`) requieren `X-API-Key: <FRAUDE_API_KEY>`.

### `GET /api/health`
Healthcheck, sin autenticación.

### `POST /api/polizas/hash`
Registra el hash de una póliza. **Rechaza duplicados** (`409`) si ya existe
un hash para ese `numero_poliza` — no se sobrescribe, para no permitir que
un hash legítimo sea reemplazado.

```bash
curl -X POST https://tu-motor-fraude.vercel.app/api/polizas/hash \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FRAUDE_API_KEY" \
  -d '{
        "numero_poliza": "POL-1",
        "tipo_documento": "CC",
        "documento_identidad": "123456789",
        "ramo": "Vida",
        "tipo_cobertura": "Individual",
        "monto_asegurado": 500000,
        "fecha_inicio_vigencia": "2026-01-01",
        "fecha_fin_vigencia": "2026-12-31"
      }'
```

Respuesta `201`: `{ "id": "...", "numero_poliza": "POL-1", "hash": "...", "fecha_creacion": "..." }`
Respuesta `409` si ya existe un hash para esa póliza.

### `POST /api/polizas/validar`

Recibe los mismos 8 campos y valida su integridad:

```bash
curl -X POST https://tu-motor-fraude.vercel.app/api/polizas/validar \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FRAUDE_API_KEY" \
  -d '{ ...mismos 8 campos... }'
```

**Lógica**:
1. Calcula el hash de los datos recibidos y lo compara contra el hash
   almacenado para ese `numero_poliza`.
2. Si coincide → `hash_coincide: true`, `verificacion: "directo"`.
3. Si NO coincide → consulta `GET /api/logs` en `poliza_seguridad`
   (`tipo_evento=Poliza&evento=Create&identificador=<numero_poliza>`),
   extrae los 8 campos del `detalle` del log, calcula su hash y lo compara
   contra el hash **almacenado** (no contra el recibido):
   - Si coincide → el log confirma la integridad del hash almacenado;
     se devuelven `datos_correctos` recuperados del log, pero
     `hash_coincide: false` (los datos recibidos en la petición seguían
     sin ser los correctos).
   - Si tampoco coincide (o no hay log) → `verificacion: "sin_confirmar"`,
     `datos_correctos: null`.

Respuesta `200` (ejemplo, caso `log_auditoria`):
```json
{
  "numero_poliza": "POL-1",
  "hash_coincide": false,
  "verificacion": "log_auditoria",
  "datos_correctos": { "numero_poliza": "POL-1", "...": "..." },
  "mensaje": "Los datos recibidos no coinciden con el hash almacenado, pero se recuperaron y confirmaron los datos correctos desde el log de auditoría."
}
```

Respuesta `404` si no hay ningún hash registrado para esa póliza.

## Configuración de Supabase

Usa el **mismo proyecto** Supabase que `poliza_seguridad`. Solo hay que
ejecutar [`sql/schema.sql`](sql/schema.sql) en el SQL Editor para crear la
tabla `poliza_hashes` (es independiente de `audit_logs`).

## Variables de entorno

Ver [`.env.example`](.env.example):

- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` — mismo proyecto que `poliza_seguridad`.
- `FRAUDE_API_KEY` — API key propia de este servicio.
- `AUDIT_SERVICE_URL`, `AUDIT_SERVICE_API_KEY` — para llamar a `poliza_seguridad`
  (URL de producción y su `AUDIT_API_KEY`).

## Desarrollo local

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements-dev.txt

copy .env.example .env        # y completa los valores
python run.py                 # sirve en http://localhost:5001
pytest
```

## Despliegue en Vercel

Igual que `poliza_seguridad`: `vercel link`, configurar las variables de
entorno en el dashboard (Production/Preview/Development), `vercel` (preview)
y `vercel --prod` (producción) cuando esté validado.

# Rally — Gate de salida a producción

Fecha: 2026-10-13. **Clasificación: candidato técnico verificable, NO despliegue certificado.**

Este documento separa explícitamente los controles que se pueden comprobar en GitHub Actions de los que requieren una instalación real. El software no debe ofrecerse como sistema empresarial certificado hasta completar ambos.

## 1. Evidencias de ingeniería disponibles

| Control | Evidencia requerida | Estado |
| --- | --- | --- |
| Compilación Python | GitHub Actions | Implementado en CI |
| Tests API/SQLite | GitHub Actions | Implementado en CI |
| PostgreSQL real y migraciones 1–6 | Base desechable con PostgreSQL 17 en CI | Implementado en CI |
| Separación de tenants / referencias cruzadas | Prueba de API y FK compuesta | Implementado en CI |
| Custodia exclusiva e idempotencia | Prueba de emisión repetida y conciliación | Implementado en CI |
| Restricción de importación Odoo por instancia | Prueba negativa entre namespaces | Implementado en CI |
| Filtro explícito ventas→trabajos | Prueba negativa cuando falta configuración | Implementado en CI |
| Dockerfile y Compose | Compilación de imagen y `docker compose config` | Implementado en CI |
| Stack local API + worker | Compose desechable, `/readyz` y autenticación | Smoke check incluido en CI |
| Preflight de configuración | `python -m ops.preflight` | Código implementado, ejecutar con secretos reales |

El resultado de CI no sustituye un ensayo sobre una copia de la base de datos de clientes ni valida dispositivos físicos. Revisar siempre el run correspondiente al SHA exacto que se va a distribuir.

## 2. Condiciones NO satisfechas por el código del repositorio

| Obligación previa al go-live | Cómo verificar | Responsable |
| --- | --- | --- |
| DNS + HTTPS/certificado válido | Navegador y verificación TLS contra dominio propio | Operaciones |
| Secretos únicos de producción | Bootstrap PostgreSQL separado del usuario no-superuser `rally_app`; Vault y `ops.preflight`, sin publicar valores | Seguridad/operaciones |
| Migración desde copia real | Replay de migraciones 1–6, integridad y reconciliación de datos | DBA |
| Conectividad Odoo/edición/empresa | Importación controlada de órdenes reales, contrato de filtrado explícito | Integraciones |
| GPS/Traccar | Posiciones reales con `valid=true`, frescura, mapeos y ausencias | Integraciones |
| RFID | Hardware real o deshabilitar expresamente la función comercial | Integraciones |
| Backup + restauración | Realizar `backup.sh` y restauración en DB separada | Operaciones |
| Alarmas y guardias operativas | Alertas /readyz, 5xx, reconcil. stale, conectores, disco y backup | Operaciones |
| Controles de privacidad laboral | Avisos/contratos, retención y acceso según jurisdicción | Legal + cliente |
| Prueba de carga y concurrencia | Carga esperada por cliente y degradación de locks PostgreSQL | Arquitectura |
| Aceptación de procesos de negocio | Ejecución, auditoría y firma de criterios por cliente | Cliente |
| Licencias y marca | Derechos de terceros y clearance de Rally/Odoo | Negocio/legal |

No crear un tag `production-certified` ni comprometer SLA hasta cerrar evidencia de estas condiciones.

## 3. Secuencia recomendada para el primer entorno

1. Congelar el commit exacto: registrar SHA e imagen construida. No desplegar automáticamente `main` mutable a clientes.
2. Generar .env.production a partir del ejemplo y gestionar secretos con permisos restrictivos.
3. Ejecutar preflight local, con variables exportadas. Ejemplo de carga en una terminal controlada:

   ```bash
   set -a
   source .env.production
   set +a
   python -m ops.preflight
   ```

   Debe salir 0 y sin imprimir secretos. Si falla, no continuar.

4. Validar `docker compose --env-file .env.production -f compose.production.yaml config --quiet`.
5. Preparar host y DNS, habilitar solo puertos 80/443, asegurar almacenamiento de PostgreSQL.
6. Arrancar stack con `docker compose --env-file .env.production -f compose.production.yaml up --build -d`.
7. Revisar `/healthz` y `/readyz`; no continuar si worker está degradado, salvo su primera ventana de arranque.
8. Crear tenant controlado y credenciales personales. Usar un conector Odoo con `source=odoo` y `scope=ODOO_INSTANCE`.
9. Definir `ODOO_WORKORDER_DOMAIN_JSON` con el cliente, verificar filas realmente elegibles y rechazar accidentalmente ventas no ligadas a servicios.
10. Registrar activos y simular transferencia/devolución; reconciliar, comprobar el caso y su historial.
11. Conectar proveedores uno a uno y registrar evidencia de aceptación y cobertura.
12. Ejecutar backup real, restauración de prueba y alertas antes de trasladar datos de clientes.

## 4. Aislamiento comercial

La **funcionalidad de custodia y órdenes** es el alcance inicial que podría salir primero tras certificarse sobre un cliente piloto. **GPS/RFID** son integraciones opcionales, y Temporal no es parte del flujo crítico automático de custodia. No presentar las tres líneas como un paquete integral certificado si el cliente no cuenta con conectividad y dispositivos verificados.

## 5. Condición de salida

**GO** únicamente para un tenant/vertical específico con infraestructura real verificada, procedimiento de rollback, backups restaurados, permisos y privacidad, y aceptación del cliente documentada.

**NO-GO** cuando no hay servidor/dominio, credenciales reales, respaldo recuperable, contrato de fuente de datos Odoo o evaluación legal correspondiente.

Esta distinción es esencial para evitar confundir "código publicable" con "sistema operacionalmente certificado".


## Endurecimiento sin ejecución de pruebas

El runtime productivo usa el rol PostgreSQL `rally_app`, con clave independiente del bootstrap de PostgreSQL. La base nueva lo crea mediante `ops/initdb/01-runtime-role.sh`; volumen PostgreSQL preexistente requiere una migración de roles revisada, nunca borrado de volumen. La API rechaza credenciales de base con privilegios globales. Los eventos de devolución se atribuyen al actor autenticado, no a un nombre arbitrario enviado por el navegador, y el sistema no considera esa acción equivalente a una firma de recepción independiente. Estos cambios deberán entrar en la campaña de pruebas posterior a esta entrega.

> Implementation update (2026-10-13): see [release 0.2](11-release-0.2.md) and [operations](10-production-operations.md). The original product/market discussion below is retained as historical context.

# RALLY — Resumen ejecutivo para Thradex / VtkALL

**Fecha:** 13 de octubre de 2026 · **Estado:** prototipo técnico MK0 + hipótesis comercial por validar.

## ¿Qué problema resolvería Rally?

Rally busca identificar la distancia entre **lo que la empresa se comprometió a realizar**, **lo que registró su ERP** y **lo que realmente se puede corroborar de la ejecución física**.

Ejemplo: una empresa asigna una cámara térmica a un técnico para una orden de trabajo. La orden se cierra, pero la cámara no ha sido formalmente devuelta. Rally detecta la inconsistencia, la registra como excepción y permite verificar la devolución.

**Propuesta de valor:** saber qué falta, quién debe resolverlo y qué evidencia demuestra su cierre.

## ¿Quién podría pagar?

Contratistas técnicos, empresas de mantenimiento, arrendamiento de equipos, operaciones con activos de alto valor y múltiples técnicos o vehículos. Deben presentar pérdidas, demoras o trabajo manual significativo; **no está demostrado todavía que quieran pagar una suscripción**.

## Tres posibles productos

1. **Rally Custody (prioridad del prototipo):** control de custodia de herramientas, asignaciones y devoluciones asociadas a trabajos.
2. **Rally Job Assurance:** evidencia y conciliación del cumplimiento de órdenes de trabajo.
3. **Rally Fabrication:** cotización y compras por superficie, merma y costos, aprovechando módulos Odoo existentes.

La antigua idea genérica de monitoreo/reintentos de integraciones compite con Pipe17, Celigo y capacidades propias de Odoo. No conviene construirla indiscriminadamente.

## Mercados

Perú para descubrimiento inicial; Ecuador o Chile para validación independiente; Bolivia y Argentina según demanda real; Brasil como expansión independiente por idioma, normativas y competencia. **No existe todavía estudio primario, contratos ni TAM certificado** para afirmar que algún país es el ganador.

## ¿Qué encontramos para evitar crear todo desde cero?

- **Odoo:** ERP de registro.
- **Traccar:** GPS abierto con API; no construir otro servidor de GPS.
- **OCA Field Service:** módulos de trabajo de campo.
- **Temporal:** procesos de excepción durables; no para cada dato GPS/RFID.
- **SDKs RFID / dispositivos existentes:** primero integrar; no fabricar hardware sin justificación.

El repositorio `odoo-engineering` reúne 7 addons candidatos, 11 fuentes de addons originales, investigación y patrones. No es un producto listo para venta; los addons originales tienen pendientes de permisos, integridad, licencias y validación Odoo 19.

## ¿Qué se ha publicado en este nuevo repositorio?

API de empresas aisladas, inventario de activos, órdenes de trabajo, entrega y devolución con idempotencia, observaciones de evidencia, conciliación, registro de auditoría y panel Rally Mission Control. Hay clientes iniciales para consultar Odoo JSON-2 y Traccar, y normalización de eventos RFID.

**No está implementado:** despliegue SaaS seguro, ERP sincronizado de punta a punta, conexión a GPS/RFID físico certificada, orquestación Temporal integrada, pagos/suscripciones, gestión de usuarios por empresa y validación legal.

## Método de reutilización

Copiar software **cuando su licencia lo permita**, adaptar, mejorar, atribuir a los autores, verificar y comercializar una solución que resuelva un problema concreto. Un GitHub público sin licencia no otorga libertad ilimitada de copia. La relación comercial oficial con Odoo y el nombre Rally requieren verificación.

## Decisión recomendada

**Sí** al laboratorio técnico y descubrimiento comercial. **No todavía** a desarrollar una plataforma completa o hardware propietario. Requerir al menos tres pilotos pagados y evidencia de repetición y retorno económico antes de aprobar una inversión mayor.

**Rally no debería vender tecnología: debería vender control y evidencia verificable de los procesos que las empresas necesitan cerrar.**

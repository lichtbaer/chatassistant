"""
Performance monitoring system for audit operations.

This module provides comprehensive monitoring, metrics collection,
and performance tracking for the audit system.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import redis
from app.core.config import settings
from app.models.audit_extended import (
    AuditEventType,
    ExtendedAuditLog,
)
from app.utils.exceptions import AuditError
from sqlalchemy import func, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AuditMetrics:
    """Audit metrics collection and tracking."""

    def __init__(self, db: Session):
        self.db = db
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_METRICS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )
        self.metrics_prefix = "audit_metrics:"
        self.performance_prefix = "audit_performance:"

    async def record_audit_event(
        self,
        event_type: AuditEventType,
        duration_ms: int,
        success: bool = True,
    ) -> None:
        """Record audit event metrics."""
        try:
            timestamp = datetime.now(UTC)
            key = f"{self.metrics_prefix}events:{timestamp.strftime('%Y%m%d:%H')}"

            # Increment event counters
            self.redis_client.hincrby(key, f"total_{event_type.value}", 1)
            if success:
                self.redis_client.hincrby(key, f"success_{event_type.value}", 1)
            else:
                self.redis_client.hincrby(key, f"failed_{event_type.value}", 1)

            # Record performance metrics
            perf_key = f"{self.performance_prefix}{event_type.value}:{timestamp.strftime('%Y%m%d:%H')}"
            self.redis_client.lpush(perf_key, duration_ms)
            self.redis_client.expire(perf_key, 86400)  # Keep for 24 hours

            # Update rolling averages
            avg_key = f"{self.performance_prefix}avg:{event_type.value}"
            current_avg = self.redis_client.get(avg_key)
            if current_avg:
                current_avg = float(current_avg)
                count = int(
                    self.redis_client.get(
                        f"{self.performance_prefix}count:{event_type.value}",
                    )
                    or 0,
                )
                new_avg = ((current_avg * count) + duration_ms) / (count + 1)
                self.redis_client.set(avg_key, new_avg)
                self.redis_client.incr(
                    f"{self.performance_prefix}count:{event_type.value}",
                )
            else:
                self.redis_client.set(avg_key, duration_ms)
                self.redis_client.set(
                    f"{self.performance_prefix}count:{event_type.value}",
                    1,
                )

        except Exception as e:
            logger.exception(f"Failed to record audit metrics: {str(e)}")

    async def record_query_performance(
        self,
        query_type: str,
        duration_ms: int,
        result_count: int,
    ) -> None:
        """Record query performance metrics."""
        try:
            timestamp = datetime.now(UTC)
            key = f"{self.performance_prefix}queries:{timestamp.strftime('%Y%m%d:%H')}"

            # Store query performance data
            query_data = {
                "type": query_type,
                "duration": duration_ms,
                "result_count": result_count,
                "timestamp": timestamp.isoformat(),
            }

            self.redis_client.lpush(key, json.dumps(query_data))
            self.redis_client.expire(key, 86400)  # Keep for 24 hours

        except Exception as e:
            logger.exception(f"Failed to record query performance: {str(e)}")

    async def record_cache_performance(
        self,
        cache_operation: str,
        hit: bool,
        duration_ms: int,
    ) -> None:
        """Record cache performance metrics."""
        try:
            timestamp = datetime.now(UTC)
            key = f"{self.performance_prefix}cache:{timestamp.strftime('%Y%m%d:%H')}"

            # Increment cache counters
            self.redis_client.hincrby(key, f"total_{cache_operation}", 1)
            if hit:
                self.redis_client.hincrby(key, f"hit_{cache_operation}", 1)
            else:
                self.redis_client.hincrby(key, f"miss_{cache_operation}", 1)

            # Record cache performance
            perf_key = f"{self.performance_prefix}cache_perf:{cache_operation}:{timestamp.strftime('%Y%m%d:%H')}"
            self.redis_client.lpush(perf_key, duration_ms)
            self.redis_client.expire(perf_key, 86400)

        except Exception as e:
            logger.exception(f"Failed to record cache performance: {str(e)}")

    async def get_performance_metrics(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        event_types: list[AuditEventType] | None = None,
    ) -> dict[str, Any]:
        """Get comprehensive performance metrics."""
        try:
            if not start_date:
                start_date = datetime.now(UTC) - timedelta(hours=24)
            if not end_date:
                end_date = datetime.now(UTC)

            metrics = {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                "event_metrics": {},
                "performance_metrics": {},
                "cache_metrics": {},
                "database_metrics": {},
            }

            # Get event metrics
            for event_type in event_types or list(AuditEventType):
                event_metrics = await self._get_event_metrics(
                    event_type,
                    start_date,
                    end_date,
                )
                metrics["event_metrics"][event_type.value] = event_metrics

            # Get performance metrics
            metrics["performance_metrics"] = await self._get_performance_metrics(
                start_date,
                end_date,
            )

            # Get cache metrics
            metrics["cache_metrics"] = await self._get_cache_metrics(
                start_date,
                end_date,
            )

            # Get database metrics
            metrics["database_metrics"] = await self._get_database_metrics(
                start_date,
                end_date,
            )

            return metrics

        except Exception as e:
            logger.exception(f"Failed to get performance metrics: {str(e)}")
            raise AuditError(f"Failed to get performance metrics: {str(e)}")

    async def get_real_time_metrics(self) -> dict[str, Any]:
        """Get real-time performance metrics."""
        try:
            current_hour = datetime.now(UTC).strftime("%Y%m%d:%H")

            metrics = {
                "timestamp": datetime.now(UTC).isoformat(),
                "current_hour": {},
                "rolling_averages": {},
                "active_alerts": {},
            }

            # Current hour metrics
            for event_type in AuditEventType:
                key = f"{self.metrics_prefix}events:{current_hour}"
                total = int(
                    self.redis_client.hget(key, f"total_{event_type.value}") or 0,
                )
                success = int(
                    self.redis_client.hget(key, f"success_{event_type.value}") or 0,
                )
                failed = int(
                    self.redis_client.hget(key, f"failed_{event_type.value}") or 0,
                )

                metrics["current_hour"][event_type.value] = {
                    "total": total,
                    "success": success,
                    "failed": failed,
                    "success_rate": (success / total * 100) if total > 0 else 0,
                }

            # Rolling averages
            for event_type in AuditEventType:
                avg_key = f"{self.performance_prefix}avg:{event_type.value}"
                avg_duration = self.redis_client.get(avg_key)
                if avg_duration:
                    metrics["rolling_averages"][event_type.value] = {
                        "avg_duration_ms": float(avg_duration),
                        "total_count": int(
                            self.redis_client.get(
                                f"{self.performance_prefix}count:{event_type.value}",
                            )
                            or 0,
                        ),
                    }

            return metrics

        except Exception as e:
            logger.exception(f"Failed to get real-time metrics: {str(e)}")
            raise AuditError(f"Failed to get real-time metrics: {str(e)}")

    async def get_performance_alerts(self) -> list[dict[str, Any]]:
        """Get performance alerts based on thresholds."""
        try:
            alerts = []
            current_hour = datetime.now(UTC).strftime("%Y%m%d:%H")

            # Check for high error rates
            for event_type in AuditEventType:
                key = f"{self.metrics_prefix}events:{current_hour}"
                total = int(
                    self.redis_client.hget(key, f"total_{event_type.value}") or 0,
                )
                failed = int(
                    self.redis_client.hget(key, f"failed_{event_type.value}") or 0,
                )

                if total > 0:
                    error_rate = (failed / total) * 100
                    if error_rate > 10:  # Alert if error rate > 10%
                        alerts.append(
                            {
                                "type": "high_error_rate",
                                "event_type": event_type.value,
                                "error_rate": error_rate,
                                "threshold": 10,
                                "severity": (
                                    "warning" if error_rate < 25 else "critical"
                                ),
                            },
                        )

            # Check for performance degradation
            for event_type in AuditEventType:
                avg_key = f"{self.performance_prefix}avg:{event_type.value}"
                avg_duration = self.redis_client.get(avg_key)

                if avg_duration:
                    avg_duration = float(avg_duration)
                    # Alert if average duration > 1000ms
                    if avg_duration > 1000:
                        alerts.append(
                            {
                                "type": "performance_degradation",
                                "event_type": event_type.value,
                                "avg_duration_ms": avg_duration,
                                "threshold": 1000,
                                "severity": (
                                    "warning" if avg_duration < 2000 else "critical"
                                ),
                            },
                        )

            return alerts

        except Exception as e:
            logger.exception(f"Failed to get performance alerts: {str(e)}")
            raise AuditError(f"Failed to get performance alerts: {str(e)}")

    # Private methods
    async def _get_event_metrics(
        self,
        event_type: AuditEventType,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get metrics for specific event type."""
        try:
            metrics = {
                "total_events": 0,
                "successful_events": 0,
                "failed_events": 0,
                "success_rate": 0,
                "avg_duration_ms": 0,
                "peak_hour": None,
                "peak_count": 0,
            }

            # Get database metrics
            query = self.db.query(ExtendedAuditLog).filter(
                ExtendedAuditLog.event_type == event_type,
                ExtendedAuditLog.timestamp >= start_date,
                ExtendedAuditLog.timestamp <= end_date,
            )

            total_events = query.count()
            successful_events = query.filter(
                ExtendedAuditLog.action_result == "success",
            ).count()
            failed_events = total_events - successful_events

            # Calculate average duration
            duration_result = (
                self.db.query(func.avg(ExtendedAuditLog.event_duration))
                .filter(
                    ExtendedAuditLog.event_type == event_type,
                    ExtendedAuditLog.timestamp >= start_date,
                    ExtendedAuditLog.timestamp <= end_date,
                    ExtendedAuditLog.event_duration.isnot(None),
                )
                .scalar()
            )

            avg_duration = float(duration_result) if duration_result else 0

            # Find peak hour
            peak_hour_query = (
                self.db.query(
                    func.date_trunc("hour", ExtendedAuditLog.timestamp).label("hour"),
                    func.count(ExtendedAuditLog.id).label("count"),
                )
                .filter(
                    ExtendedAuditLog.event_type == event_type,
                    ExtendedAuditLog.timestamp >= start_date,
                    ExtendedAuditLog.timestamp <= end_date,
                )
                .group_by(text("hour"))
                .order_by(text("count DESC"))
                .first()
            )

            metrics.update(
                {
                    "total_events": total_events,
                    "successful_events": successful_events,
                    "failed_events": failed_events,
                    "success_rate": (
                        (successful_events / total_events * 100)
                        if total_events > 0
                        else 0
                    ),
                    "avg_duration_ms": avg_duration,
                    "peak_hour": (
                        peak_hour_query.hour.isoformat() if peak_hour_query else None
                    ),
                    "peak_count": peak_hour_query.count if peak_hour_query else 0,
                },
            )

            return metrics

        except Exception as e:
            logger.exception(f"Failed to get event metrics: {str(e)}")
            return {}

    async def _get_performance_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get overall performance metrics."""
        try:
            return {
                "total_queries": 0,
                "avg_query_duration_ms": 0,
                "slow_queries": 0,
                "cache_hit_rate": 0,
                "database_connections": 0,
            }

            # This would implement actual performance metrics collection
            # For now, return placeholder data

        except Exception as e:
            logger.exception(f"Failed to get performance metrics: {str(e)}")
            return {}

    async def _get_cache_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get cache performance metrics."""
        try:
            return {
                "total_operations": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "hit_rate": 0,
                "avg_operation_duration_ms": 0,
            }

            # This would implement actual cache metrics collection
            # For now, return placeholder data

        except Exception as e:
            logger.exception(f"Failed to get cache metrics: {str(e)}")
            return {}

    async def _get_database_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get database performance metrics."""
        try:
            return {
                "total_queries": 0,
                "slow_queries": 0,
                "avg_query_duration_ms": 0,
                "connection_pool_usage": 0,
                "deadlocks": 0,
            }

            # This would implement actual database metrics collection
            # For now, return placeholder data

        except Exception as e:
            logger.exception(f"Failed to get database metrics: {str(e)}")
            return {}


class AuditPerformanceMonitor:
    """Audit performance monitoring and alerting."""

    def __init__(self, db: Session):
        self.db = db
        self.metrics = AuditMetrics(db)
        self.alert_thresholds = {
            "error_rate": 10.0,  # 10% error rate threshold
            "avg_duration": 1000,  # 1000ms average duration threshold
            "peak_events": 1000,  # 1000 events per hour threshold
        }

    async def start_monitoring(self) -> None:
        """Start the performance monitoring system."""
        try:
            logger.info("Starting audit performance monitoring")

            # Start background monitoring tasks
            asyncio.create_task(self._monitor_performance())
            asyncio.create_task(self._cleanup_old_metrics())

        except Exception as e:
            logger.exception(f"Failed to start performance monitoring: {str(e)}")

    async def _monitor_performance(self) -> None:
        """Background task to monitor performance."""
        while True:
            try:
                # Get current metrics
                await self.metrics.get_real_time_metrics()

                # Check for alerts
                alerts = await self.metrics.get_performance_alerts()

                # Process alerts
                for alert in alerts:
                    await self._process_alert(alert)

                # Wait before next check
                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.exception(f"Error in performance monitoring: {str(e)}")
                await asyncio.sleep(60)

    async def _cleanup_old_metrics(self) -> None:
        """Background task to cleanup old metrics."""
        while True:
            try:
                # Cleanup metrics older than 30 days
                datetime.now(UTC) - timedelta(days=30)

                # This would implement actual cleanup logic
                # For now, just log the cleanup
                logger.info("Cleaning up old audit metrics")

                # Wait before next cleanup
                await asyncio.sleep(3600)  # Cleanup every hour

            except Exception as e:
                logger.exception(f"Error in metrics cleanup: {str(e)}")
                await asyncio.sleep(3600)

    async def _process_alert(self, alert: dict[str, Any]) -> None:
        """Process performance alerts."""
        try:
            logger.warning(f"Performance alert: {alert}")

            # Here you would implement actual alert processing:
            # - Send email notifications
            # - Create incident tickets
            # - Trigger automated responses
            # - Update monitoring dashboards

        except Exception as e:
            logger.exception(f"Failed to process alert: {str(e)}")

    async def get_monitoring_dashboard(self) -> dict[str, Any]:
        """Get comprehensive monitoring dashboard data."""
        try:
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "overview": await self._get_overview_metrics(),
                "performance": await self._get_performance_overview(),
                "alerts": await self.metrics.get_performance_alerts(),
                "trends": await self._get_performance_trends(),
            }

        except Exception as e:
            logger.exception(f"Failed to get monitoring dashboard: {str(e)}")
            raise AuditError(f"Failed to get monitoring dashboard: {str(e)}")

    async def _get_overview_metrics(self) -> dict[str, Any]:
        """Get overview metrics for dashboard."""
        try:
            # Get current hour metrics
            current_hour = datetime.now(UTC).strftime("%Y%m%d:%H")

            total_events = 0
            total_errors = 0

            for event_type in AuditEventType:
                key = f"{self.metrics.metrics_prefix}events:{current_hour}"
                total = int(
                    self.metrics.redis_client.hget(key, f"total_{event_type.value}")
                    or 0,
                )
                failed = int(
                    self.metrics.redis_client.hget(key, f"failed_{event_type.value}")
                    or 0,
                )

                total_events += total
                total_errors += failed

            return {
                "total_events_current_hour": total_events,
                "total_errors_current_hour": total_errors,
                "error_rate_current_hour": (
                    (total_errors / total_events * 100) if total_events > 0 else 0
                ),
                "system_status": (
                    "healthy"
                    if total_errors / total_events < 0.1
                    else "degraded" if total_events > 0 else "unknown"
                ),
            }

        except Exception as e:
            logger.exception(f"Failed to get overview metrics: {str(e)}")
            return {}

    async def _get_performance_overview(self) -> dict[str, Any]:
        """Get performance overview for dashboard."""
        try:
            performance = {
                "avg_response_times": {},
                "throughput": {},
                "resource_usage": {},
            }

            # Get average response times for each event type
            for event_type in AuditEventType:
                avg_key = f"{self.metrics.performance_prefix}avg:{event_type.value}"
                avg_duration = self.metrics.redis_client.get(avg_key)
                if avg_duration:
                    performance["avg_response_times"][event_type.value] = float(
                        avg_duration,
                    )

            return performance

        except Exception as e:
            logger.exception(f"Failed to get performance overview: {str(e)}")
            return {}

    async def _get_performance_trends(self) -> dict[str, Any]:
        """Get performance trends for dashboard."""
        try:
            trends = {
                "event_volume_trend": [],
                "error_rate_trend": [],
                "response_time_trend": [],
            }

            # Get trends for the last 24 hours
            for hour in range(24):
                timestamp = datetime.now(UTC) - timedelta(hours=hour)
                hour_key = timestamp.strftime("%Y%m%d:%H")

                # Calculate event volume for this hour
                total_events = 0
                total_errors = 0

                for event_type in AuditEventType:
                    key = f"{self.metrics.metrics_prefix}events:{hour_key}"
                    total = int(
                        self.metrics.redis_client.hget(key, f"total_{event_type.value}")
                        or 0,
                    )
                    failed = int(
                        self.metrics.redis_client.hget(
                            key,
                            f"failed_{event_type.value}",
                        )
                        or 0,
                    )

                    total_events += total
                    total_errors += failed

                trends["event_volume_trend"].append(
                    {
                        "timestamp": timestamp.isoformat(),
                        "value": total_events,
                    },
                )

                trends["error_rate_trend"].append(
                    {
                        "timestamp": timestamp.isoformat(),
                        "value": (
                            (total_errors / total_events * 100)
                            if total_events > 0
                            else 0
                        ),
                    },
                )

            return trends

        except Exception as e:
            logger.exception(f"Failed to get performance trends: {str(e)}")
            return {}


# Global instances
audit_metrics = None
audit_monitor = None


def get_audit_metrics(db: Session) -> AuditMetrics:
    """Get audit metrics instance."""
    global audit_metrics
    if audit_metrics is None:
        audit_metrics = AuditMetrics(db)
    return audit_metrics


def get_audit_monitor(db: Session) -> AuditPerformanceMonitor:
    """Get audit performance monitor instance."""
    global audit_monitor
    if audit_monitor is None:
        audit_monitor = AuditPerformanceMonitor(db)
    return audit_monitor

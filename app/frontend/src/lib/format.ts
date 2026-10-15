// Formato es-ES de numeros, distancias, horas y fechas (pantallas §0)

const decimal1 = new Intl.NumberFormat("es-ES", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
});

const upTo1 = new Intl.NumberFormat("es-ES", {
    maximumFractionDigits: 1,
    useGrouping: "always",
});

export function formatScore(value: number): string {
    return decimal1.format(value);
}

export function formatNumber(value: number): string {
    return upTo1.format(value);
}

export function formatDistance(meters: number): string {
    if (meters < 1000) {
        return `${Math.round(meters / 10) * 10} m`;
    }
    const km = meters / 1000;
    return `${km >= 10 ? Math.round(km) : decimal1.format(km)} km`;
}

export function formatMinutes(minutes: number): string {
    const total = Math.round(minutes);
    if (total < 60) {
        return `${total} min`;
    }
    const h = Math.floor(total / 60);
    const m = total % 60;
    return m === 0 ? `${h} h` : `${h} h ${m} min`;
}

// Las horas del contrato llegan en hora local de Madrid sin zona: se toma HH:MM
export function formatHour(datetime: string): string {
    const match = /T(\d{2}):(\d{2})/.exec(datetime);
    return match ? `${match[1]}:${match[2]}` : datetime;
}

// «14/10 18:00»
export function formatSourceDate(datetime: string): string {
    const match = /^\d{4}-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(datetime);
    if (!match) {
        return datetime;
    }
    const [, month, day, hh, mm] = match;
    return `${day}/${month} ${hh}:${mm}`;
}

// «hace 12 min», «hace 3 h», «hace 3 dias»
export function formatTimeAgo(datetime: string, now: Date = new Date()): string {
    const then = new Date(datetime);
    const minutes = Math.max(
        0,
        Math.round((now.getTime() - then.getTime()) / 60000),
    );
    if (minutes < 1) {
        return "ahora mismo";
    }
    if (minutes < 60) {
        return `hace ${minutes} min`;
    }
    const hours = Math.round(minutes / 60);
    if (hours < 24) {
        return `hace ${hours} h`;
    }
    const days = Math.round(hours / 24);
    return days === 1 ? "hace 1 día" : `hace ${days} días`;
}

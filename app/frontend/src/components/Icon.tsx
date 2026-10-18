interface IconProps {
    // nombre de Material Symbols (p. ej. "directions_run")
    name: string;
}

const ICON_CLASSES: Record<string, string> = {
    air: "icon-air",
    basketball: "icon-basketball",
    bench: "icon-bench",
    arrow_left: "icon-arrow_left",
    auto_awesome: "icon-random",
    bike: "icon-bike1",
    calendar_clock: "icon-calendar_clock",
    close: "icon-close",
    eco: "icon-eco",
    elderly: "icon-elderly",
    ecg: "icon-ecg",
    family: "icon-family",
    forest: "icon-forest",
    grass: "icon-grass",
    gym: "icon-gym",
    location_off: "icon-location_off",
    location_on: "icon-location_on",
    location_city: "icon-location_on",
    menu: "icon-menu",
    mountain: "icon-mountain",
    nature: "icon-nature",
    navigation: "icon-navigation",
    near_me: "icon-navigation",
    pets: "icon-pets",
    padel: "icon-padel",
    pool: "icon-pool",
    playground: "icon-playground",
    recycle: "icon-recycle",
    random: "icon-random",
    route: "icon-route",
    running: "icon-running",
    search: "icon-search",
    settings: "icon-settings",
    shopping_cart: "icon-shopping_cart",
    soccer: "icon-soccer",
    stadium: "icon-stadium",
    tennis: "icon-tennis",
    temperature: "icon-temperature",
    walk: "icon-walk",
    water: "icon-water",
    add: "icon-add",
    remove: "icon-remove",
    park: "icon-eco",
};

export function hasIcon(name: string): boolean {
    return name in ICON_CLASSES;
}

export default function Icon({ name }: IconProps) {
    const iconClass = ICON_CLASSES[name];
    if (!iconClass) return null;
    return <span className={`icon ${iconClass} gomad-component gomad-icon`} aria-hidden="true" data-icon={name} />;
}

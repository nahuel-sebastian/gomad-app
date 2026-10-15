import { useEffect, type ReactNode } from "react";

interface PageHeadingProps {
    children: ReactNode;
    // texto del titulo del documento; por defecto, el del h1 si es texto
    title?: string;
    className?: string;
    id?: string;
}

// h1 de cada pantalla: pone document.title y recibe el foco al navegar (Layout)
export default function PageHeading({
    children,
    title,
    className,
    id,
}: PageHeadingProps) {
    const text = title ?? (typeof children === "string" ? children : "");

    useEffect(() => {
        document.title = text ? `${text} · GoMad` : "GoMad";
    }, [text]);

    return (
        <h1 id={id} className={className} tabIndex={-1}>
            {children}
        </h1>
    );
}

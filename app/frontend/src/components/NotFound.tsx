import { Link } from "react-router";
import PageHeading from "./PageHeading";

export default function NotFound() {
    return (
        <section className="container page gomad-component gomad-not-found">
            <PageHeading className="view-title">Página no encontrada</PageHeading>
            <p className="view-subtitle">
                La dirección no corresponde a ninguna pantalla de GoMad.
            </p>
            <Link to="/" className="button button--primary gomad-action gomad-action-go-home">
                Ir al inicio
            </Link>
        </section>
    );
}

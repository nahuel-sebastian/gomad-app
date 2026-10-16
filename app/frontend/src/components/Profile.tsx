import PageHeading from "./PageHeading";
import PreferencesForm from "./PreferencesForm";

export default function Profile() {
    return (
        <section className="container page gomad-component gomad-profile" aria-labelledby="perfil-titulo">
            <PageHeading className="view-title" id="perfil-titulo">
                Tus preferencias
            </PageHeading>
            <p className="view-subtitle">
                Ajustan la nota y los filtros de las recomendaciones. Se guardan solo mientras tienes la página
                abierta; nunca guardamos tu ubicación.
            </p>
            <div className="panel">
                <PreferencesForm />
            </div>
        </section>
    );
}

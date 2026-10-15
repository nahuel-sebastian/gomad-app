import PageHeading from "./PageHeading";

// Pantalla todavia sin construir: solo su h1
export default function ComingSoon({ title }: { title: string }) {
    return (
        <section className="container page">
            <PageHeading className="view-title">{title}</PageHeading>
            <p className="view-subtitle">Próximamente.</p>
        </section>
    );
}

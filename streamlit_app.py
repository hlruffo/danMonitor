import streamlit as st
import pandas as pd
import json
from datetime import datetime
import requests
from site_voos_gerais import generate_url, fetch_price_from_url

def load_data():
    try:
        with open('dados.json', 'r') as f:
            return json.load(f)
    except:
        return []

def save_data(data):
    with open('dados.json', 'w') as f:
        json.dump(data, f, indent=4)

def main():
    st.set_page_config(page_title="Sistema de Monitoramento de Voos", layout="wide")
    st.title("Sistema de Monitoramento de Voos")

    # Sidebar for adding new entries
    with st.sidebar:
        st.header("Adicionar Novo Voo")
        with st.form("new_flight"):
            cliente = st.text_input("Cliente")
            telefone = st.text_input("Telefone")
            origem = st.text_input("Origem")
            data_ida = st.date_input("Data Ida")
            destino = st.text_input("Destino")
            data_volta = st.date_input("Data Volta", value=None, key="data_volta")
            preco_desejado = st.number_input("Preço Desejado", min_value=0.0)
            
            submitted = st.form_submit_button("Adicionar Voo")
            if submitted:
                data = load_data()
                new_entry = {
                    "Cliente": cliente,
                    "Telefone": telefone,
                    "Origem": origem,
                    "Data_Ida": data_ida.strftime("%Y-%m-%d"),
                    "Destino": destino,
                    "Data_Volta": data_volta.strftime("%Y-%m-%d") if data_volta else None,
                    "Preco": "A processar",
                    "Preco_Desejado": preco_desejado,
                    "URL_cliente": generate_url(origem, destino, data_ida.strftime("%Y-%m-%d"), 
                                             data_volta.strftime("%Y-%m-%d") if data_volta else None),
                    "Link_Whatsapp": ""
                }
                data.append(new_entry)
                save_data(data)
                st.success("Voo adicionado com sucesso!")

    # Main content
    tab1, tab2 = st.tabs(["Tabela de Voos", "Upload Excel"])

    with tab1:
        data = load_data()
        if data:
            df = pd.DataFrame(data)
            
            # Filters
            col1, col2, col3 = st.columns(3)
            with col1:
                cliente_filter = st.text_input("Filtrar por Cliente")
            with col2:
                origem_filter = st.text_input("Filtrar por Origem")
            with col3:
                destino_filter = st.text_input("Filtrar por Destino")

            # Apply filters
            if cliente_filter:
                df = df[df['Cliente'].str.contains(cliente_filter, case=False)]
            if origem_filter:
                df = df[df['Origem'].str.contains(origem_filter, case=False)]
            if destino_filter:
                df = df[df['Destino'].str.contains(destino_filter, case=False)]

            # Display table with action buttons
            for index, row in df.iterrows():
                with st.expander(f"{row['Cliente']} - {row['Origem']} → {row['Destino']}"):
                    col1, col2, col3, col4 = st.columns([3,2,2,1])
                    with col1:
                        st.write(f"**Preço Atual:** R$ {row['Preco']}")
                        st.write(f"**Preço Desejado:** R$ {row['Preco_Desejado']}")
                    with col2:
                        st.write(f"**Data Ida:** {row['Data_Ida']}")
                        st.write(f"**Data Volta:** {row['Data_Volta']}")
                    with col3:
                        if st.button("Atualizar Preço", key=f"update_{index}"):
                            new_price = fetch_price_from_url(row['URL_cliente'])
                            data[index]['Preco'] = new_price
                            save_data(data)
                            st.success(f"Preço atualizado: R$ {new_price}")
                    with col4:
                        if st.button("Remover", key=f"remove_{index}"):
                            data.pop(index)
                            save_data(data)
                            st.success("Voo removido com sucesso!")
                            st.rerun()

    with tab2:
        st.header("Upload de Excel")
        uploaded_file = st.file_uploader("Escolha um arquivo Excel", type=['xlsx'])
        if uploaded_file:
            try:
                df = pd.read_excel(uploaded_file)
                st.write("Preview dos dados:")
                st.dataframe(df)
                if st.button("Confirmar Upload"):
                    # Process the Excel file similar to the Flask route
                    data = load_data()
                    for _, row in df.iterrows():
                        new_entry = {
                            "Cliente": row["Cliente"],
                            "Telefone": row["Telefone"],
                            "Origem": row["Origem"],
                            "Data_Ida": row["Data_Ida"].strftime("%Y-%m-%d"),
                            "Destino": row["Destino"],
                            "Data_Volta": row["Data_Volta"].strftime("%Y-%m-%d") if pd.notna(row["Data_Volta"]) else None,
                            "Preco": "A processar",
                            "Preco_Desejado": row.get("Preco_Desejado", None),
                            "URL_cliente": generate_url(
                                row["Origem"], row["Destino"], 
                                row["Data_Ida"].strftime("%Y-%m-%d"),
                                row["Data_Volta"].strftime("%Y-%m-%d") if pd.notna(row["Data_Volta"]) else None
                            ),
                            "Link_Whatsapp": ""
                        }
                        data.append(new_entry)
                    save_data(data)
                    st.success("Dados importados com sucesso!")
            except Exception as e:
                st.error(f"Erro ao processar arquivo: {str(e)}")

if __name__ == "__main__":
    main()

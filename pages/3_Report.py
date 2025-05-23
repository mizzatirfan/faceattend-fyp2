import streamlit as st
import pandas as pd
import datetime
from Home import face_rec
st.set_page_config(page_title='Reporting',layout='wide')

st.subheader('Reporting')

#Retrive logs data and show in Report.py
#extract data from redis list
name = 'attendance:logs'
def load_logs(name,end=-1):
    logs_list = face_rec.r.lrange(name,start=0,end=end) #extract all data from the redis databse
    return logs_list

# table to show the info
tab1, tab2, tab3 = st.tabs(['Registered Data','Logs','Attendance Report'])

with tab1:
    if st.button('Refresh Data'):
        #Retrive the data from Redis Database
        with st.spinner('Retriving Data from Redis DB...'):
            redis_face_db = face_rec.retrive_data(name='academy:register')
            st.dataframe(redis_face_db[['Name','Role']])

with tab2:
    if st.button('Refresh Logs'):
        st.write(load_logs(name=name))

with tab3:
    st.subheader("Attendance Report")

    #load logs into attribute logs_list
    logs_list = load_logs(name=name)

    #step 1 convert the logs that in list of bytes into list of string
    convert_byte_to_string = lambda x: x.decode('utf-8')
    logs_list_string = list(map(convert_byte_to_string, logs_list))

    #step 2 split string by @ and created nested list
    split_string = lambda x: x.split('@')
    logs_nested_list = list(map(split_string, logs_list_string))
    #convert nested list info into dataframe

    logs_df = pd.DataFrame(logs_nested_list, columns=['Name', 'Role', 'Timestamp'])
    
    #step 3 Time based Analysis or Report
    logs_df['Timestamp'] = pd.to_datetime(logs_df['Timestamp'])
    logs_df['Date'] = logs_df['Timestamp'].dt.date

    #step 3.1 : Cal. Intime and Outtime
    #In time: At which person is first detected in that day (min timestamp of date)
    #Out time:At which person is last detected in that day (max timestamp of date)

    report_df = logs_df.groupby(by=['Date', 'Name', 'Role']).agg(
    In_time=pd.NamedAgg(column='Timestamp', aggfunc='min'),  # In time
    Out_time=pd.NamedAgg(column='Timestamp', aggfunc='max')  # Out time
).reset_index()

    report_df['In_time'] = pd.to_datetime(report_df['In_time'])
    report_df['Out_time'] = pd.to_datetime(report_df['Out_time'])

    report_df['Duration'] = report_df['Out_time'] - report_df['In_time']

    #step 4 : Marking person is present or absent
    all_dates = report_df['Date'].unique()
    name_role = report_df[['Name', 'Role']].drop_duplicates().values.tolist()


    date_name_rol_zip = []
    for dt in all_dates:
        for name, role in name_role:
            date_name_rol_zip.append([dt, name, role])
   
    date_name_rol_zip_df = pd.DataFrame(date_name_rol_zip, columns=['Date', 'Name', 'Role'])
    #left join with report_Df

    date_name_role_zip = pd.merge(date_name_rol_zip_df, report_df, how='left', on=['Date','Name','Role'])

    # Calculate seconds and hours only if Duration exists
    date_name_role_zip['Duration_seconds'] = date_name_role_zip['Duration'].dt.total_seconds().fillna(0).astype(int)
    date_name_role_zip['Duration_hours'] = date_name_role_zip['Duration_seconds'] / 3600

    #date_name_rol_zip_df['Duration_seconds'] = date_name_role_zip['Duration'].dt.seconds
    date_name_rol_zip_df['Duration_hours'] = date_name_role_zip['Duration_seconds'] / 3600

    def status_marker(x):

        if pd.Series(x).isnull().all():
            return 'Absent'
        
        elif x >= 0 and x < 1:
            return 'Absent (Less than 1 hr)'
        
        elif x >= 1 and x < 4:
            return 'Half Day(less than 4 hours)'
        
        elif x>= 4 and x < 6:
            return 'Half Day'
        
        elif x >= 6:
            return 'Present'

    date_name_role_zip['Status'] = date_name_role_zip['Duration_hours'].apply(status_marker)
    date_name_rol_zip_df['Status'] = date_name_role_zip['Duration_hours'].apply(status_marker)
    
    st.dataframe(date_name_role_zip)

    #tab
    t1, t2 = st.tabs(['Complete Report','Filter Report'])

    with t1:
        st.subheader("Complete Report")
        st.dataframe(date_name_rol_zip_df)
    
    with t2:
        st.subheader('Search Records')

        #Date

        date_in = st.date_input('Filter_date',datetime.datetime.now().date())
        
        #Filter the person names
        name_list = date_name_rol_zip_df['Name'].unique().tolist()
        name_in = st.selectbox('Select Name',['ALL']+name_list)

        #FIlter teacher or student (role)
        role_list = date_name_rol_zip_df['Role'].unique().tolist()
        role_in = st.selectbox('Select Role',['ALL']+role_list)

        #Filter the duration
        duration_in = st.slider('filter the duratin in hours greater than', 0, 15, 6)

        #status
        status_list = date_name_rol_zip_df['Status'].dropna().unique().tolist()
        status_in = st.multiselect('Select the status', ['All']+status_list)

        if st.button('Submit'):
            date_name_rol_zip_df['Date'] = date_name_rol_zip_df['Date'].astype(str)

            #filter date
            filter_df = date_name_rol_zip_df.query(f'Date =="{date_in}"')
        
            #filter name
            if name_in == 'ALL':
                filter_df = filter_df
            elif name_in != 'ALL':
                filter_df = filter_df.query(f'Name =="{name_in}"')
            else:
                filter_df = filter_df
            
            #filter role
            if role_in == 'ALL':
                filter_df = filter_df
            elif role_in != 'All':
                filter_df = filter_df.query(f'Role =="{role_in}"')
            else:
                filter_df = filter_df
            

            #filter duration
            if duration_in > 0:
                filter_df = filter_df.query(f'Duration_hours > {duration_in}')
            
            #filter status
            
            if 'ALL' in status_in:
                filter_df = filter_df

            elif len(status_in) > 0:
                # Create temp boolean column
                filter_df['Status_condition'] = filter_df['Status'].apply(lambda x: True if x in status_in else False)

                # Filter by that column (case-sensitive!)
                filter_df = filter_df[filter_df['Status_condition'] == True]

                # Clean up
                filter_df.drop(columns='Status_condition', inplace=True)

            
            else:
                filter_df = filter_df
            

            st.dataframe(filter_df)

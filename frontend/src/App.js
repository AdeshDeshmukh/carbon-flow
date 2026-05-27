import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000/api';

function App() {
  const [emissions, setEmissions] = useState([]);
  const [summary, setSummary] = useState({ scope_totals: [], grand_total_co2e_kg: 0 });
  const [uploadStatus, setUploadStatus] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [sourceType, setSourceType] = useState('sap');
  const [companyId, setCompanyId] = useState(1);
  const [loading, setLoading] = useState(false);

  // Fetch emissions and summary on mount
  useEffect(() => {
    fetchEmissions();
    fetchSummary();
  }, []);

  // Fetch emissions from API
  const fetchEmissions = async () => {
    try {
      const response = await axios.get(`${API_URL}/emissions/`);
      setEmissions(response.data.results || response.data);
    } catch (error) {
      console.error('Error fetching emissions:', error);
      setUploadStatus('Error loading emissions');
    }
  };

  // Fetch summary from API
  const fetchSummary = async () => {
    try {
      const response = await axios.get(`${API_URL}/emissions/summary/`);
      setSummary(response.data);
    } catch (error) {
      console.error('Error fetching summary:', error);
    }
  };

  // Handle file selection
  const handleFileChange = (e) => {
    setSelectedFile(e.target.files[0]);
  };

  // Handle file upload
  const handleUpload = async () => {
    if (!selectedFile) {
      setUploadStatus('Please select a file');
      return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('source_type', sourceType);
    formData.append('company_id', companyId);

    setLoading(true);
    try {
      const response = await axios.post(`${API_URL}/ingestion-jobs/upload/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setUploadStatus(`✅ Success! Processed ${response.data.successful_rows} rows`);
      setSelectedFile(null);
      setTimeout(() => setUploadStatus(''), 3000);
      fetchEmissions();
      fetchSummary();
    } catch (error) {
      setUploadStatus(`❌ Error: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Handle approve/reject
  const handleApprove = async (emissionId, newStatus) => {
    try {
      await axios.patch(`${API_URL}/emissions/${emissionId}/approve/`, {
        status: newStatus,
        reviewed_by: 'admin'
      });
      fetchEmissions();
      fetchSummary();
    } catch (error) {
      console.error('Error updating status:', error);
    }
  };

  // Get status badge with color
  const getStatusBadge = (status) => {
    const colors = {
      pending: '#fef3c7',
      approved: '#d1fae5',
      rejected: '#fee2e2',
      locked: '#e5e7eb'
    };
    return (
      <span style={{
        backgroundColor: colors[status] || '#f3f4f6',
        padding: '4px 12px',
        borderRadius: '4px',
        fontSize: '12px',
        fontWeight: 'bold',
        textTransform: 'uppercase'
      }}>
        {status}
      </span>
    );
  };

  return (
    <div style={{ fontFamily: 'Arial, sans-serif' }}>
      {/* Header */}
      <header style={{
        background: 'linear-gradient(135deg, #1e40af 0%, #3b82f6 100%)',
        color: 'white',
        padding: '30px 20px',
        textAlign: 'center',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
      }}>
        <h1 style={{ margin: '0 0 10px 0' }}>🌱 Carbon Flow Dashboard</h1>
        <p style={{ margin: 0, opacity: 0.9 }}>Emissions Data Management Platform</p>
      </header>

      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '30px 20px' }}>
        {/* Summary Cards */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '20px',
          marginBottom: '40px'
        }}>
          {summary.scope_totals && summary.scope_totals.map((scope, idx) => (
            <div key={idx} style={{
              backgroundColor: 'white',
              borderRadius: '8px',
              padding: '20px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
              border: '1px solid #e5e7eb'
            }}>
              <h3 style={{ margin: '0 0 15px 0', color: '#374151' }}>{scope.scope}</h3>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1f2937', marginBottom: '10px' }}>
                {parseFloat(scope.total_co2e_kg).toLocaleString('en-US', { maximumFractionDigits: 2 })} kg CO₂e
              </div>
              <div style={{ fontSize: '12px', color: '#6b7280' }}>
                🔄 Pending: {scope.pending_count} | ✅ Approved: {scope.approved_count}
              </div>
            </div>
          ))}
        </div>

        {/* Upload Section */}
        <div style={{
          backgroundColor: 'white',
          borderRadius: '8px',
          padding: '25px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
          marginBottom: '40px',
          border: '1px solid #e5e7eb'
        }}>
          <h2 style={{ margin: '0 0 20px 0', color: '#1f2937' }}>📤 Upload Emissions Data</h2>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'auto auto 1fr auto', gap: '10px', alignItems: 'center', marginBottom: '15px' }}>
            <select
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value)}
              style={{
                padding: '8px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '4px',
                fontSize: '14px',
                cursor: 'pointer'
              }}
            >
              <option value="sap">SAP (Materials)</option>
              <option value="utility">Utility (Electricity)</option>
              <option value="travel">Travel (Flights)</option>
            </select>

            <input
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              style={{
                padding: '8px',
                border: '1px solid #d1d5db',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            />

            <div></div>

            <button
              onClick={handleUpload}
              disabled={loading || !selectedFile}
              style={{
                backgroundColor: loading || !selectedFile ? '#d1d5db' : '#10b981',
                color: 'white',
                border: 'none',
                padding: '10px 20px',
                borderRadius: '4px',
                cursor: loading || !selectedFile ? 'not-allowed' : 'pointer',
                fontWeight: 'bold',
                transition: 'background-color 0.3s'
              }}
            >
              {loading ? '⏳ Uploading...' : '📤 Upload'}
            </button>
          </div>

          {uploadStatus && (
            <div style={{
              padding: '12px',
              marginTop: '15px',
              backgroundColor: uploadStatus.includes('Error') ? '#fef2f2' : '#f0fdf4',
              border: `1px solid ${uploadStatus.includes('Error') ? '#fee2e2' : '#dcfce7'}`,
              borderRadius: '4px',
              color: uploadStatus.includes('Error') ? '#991b1b' : '#166534',
              fontSize: '14px'
            }}>
              {uploadStatus}
            </div>
          )}
        </div>

        {/* Emissions Table */}
        <div style={{
          backgroundColor: 'white',
          borderRadius: '8px',
          padding: '25px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
          border: '1px solid #e5e7eb',
          overflowX: 'auto'
        }}>
          <h2 style={{ margin: '0 0 20px 0', color: '#1f2937' }}>📋 Emissions Records</h2>
          
          <table style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: '14px'
          }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e5e7eb', backgroundColor: '#f9fafb' }}>
                <th style={{ textAlign: 'left', padding: '12px', fontWeight: 'bold', color: '#374151', textTransform: 'uppercase', fontSize: '12px' }}>Date</th>
                <th style={{ textAlign: 'left', padding: '12px', fontWeight: 'bold', color: '#374151', textTransform: 'uppercase', fontSize: '12px' }}>Scope</th>
                <th style={{ textAlign: 'left', padding: '12px', fontWeight: 'bold', color: '#374151', textTransform: 'uppercase', fontSize: '12px' }}>Category</th>
                <th style={{ textAlign: 'left', padding: '12px', fontWeight: 'bold', color: '#374151', textTransform: 'uppercase', fontSize: '12px' }}>Original Value</th>
                <th style={{ textAlign: 'right', padding: '12px', fontWeight: 'bold', color: '#374151', textTransform: 'uppercase', fontSize: '12px' }}>CO₂e (kg)</th>
                <th style={{ textAlign: 'center', padding: '12px', fontWeight: 'bold', color: '#374151', textTransform: 'uppercase', fontSize: '12px' }}>Status</th>
                <th style={{ textAlign: 'center', padding: '12px', fontWeight: 'bold', color: '#374151', textTransform: 'uppercase', fontSize: '12px' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {emissions.map((emission, idx) => (
                <tr key={emission.id} style={{
                  borderBottom: '1px solid #e5e7eb',
                  backgroundColor: idx % 2 === 0 ? 'white' : '#f9fafb',
                  transition: 'background-color 0.2s'
                }}>
                  <td style={{ padding: '12px' }}>{emission.activity_date}</td>
                  <td style={{ padding: '12px' }}>{emission.scope}</td>
                  <td style={{ padding: '12px' }}>{emission.category}</td>
                  <td style={{ padding: '12px' }}>{emission.original_value} {emission.original_unit}</td>
                  <td style={{ padding: '12px', textAlign: 'right', fontWeight: 'bold', color: '#dc2626' }}>
                    {parseFloat(emission.co2e_kg).toLocaleString('en-US', { maximumFractionDigits: 2 })}
                  </td>
                  <td style={{ padding: '12px', textAlign: 'center' }}>{getStatusBadge(emission.status)}</td>
                  <td style={{ padding: '12px', textAlign: 'center' }}>
                    {emission.status === 'pending' && (
                      <>
                        <button
                          onClick={() => handleApprove(emission.id, 'approved')}
                          style={{
                            backgroundColor: '#10b981',
                            color: 'white',
                            border: 'none',
                            padding: '6px 12px',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            marginRight: '5px',
                            fontSize: '12px',
                            fontWeight: 'bold'
                          }}
                        >
                          ✓ Approve
                        </button>
                        <button
                          onClick={() => handleApprove(emission.id, 'rejected')}
                          style={{
                            backgroundColor: '#ef4444',
                            color: 'white',
                            border: 'none',
                            padding: '6px 12px',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: 'bold'
                          }}
                        >
                          ✕ Reject
                        </button>
                      </>
                    )}
                    {emission.status !== 'pending' && <span style={{ color: '#6b7280' }}>—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {emissions.length === 0 && (
            <div style={{
              textAlign: 'center',
              padding: '40px',
              color: '#6b7280'
            }}>
              No emissions records yet. Upload a CSV file to get started.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;

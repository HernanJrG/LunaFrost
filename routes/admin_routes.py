"""
Admin routes for LunaFrost admin portal
"""
from flask import Blueprint, render_template, request, session, jsonify, abort
from services.admin_service import is_admin_authorized, log_admin_action, get_client_ip
from database.database import db_session_scope
from database.db_models import GlobalModelPricing
from sqlalchemy import or_

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.before_request
def check_admin_auth():
    """Middleware to enforce admin authentication on all admin routes"""
    username = session.get('username')
    
    if not is_admin_authorized(request, username):
        client_ip = get_client_ip(request)
        abort(403)


@admin_bp.route('/')
def dashboard():
    """Admin dashboard home page"""
    username = session.get('username')
    log_admin_action(username, "Accessed admin dashboard")
    
    return render_template('admin/dashboard.html', username=username)


@admin_bp.route('/pricing')
def pricing_page():
    """Admin pricing management page"""
    username = session.get('username')
    log_admin_action(username, "Accessed pricing management")
    
    return render_template('admin/pricing.html', username=username)


@admin_bp.route('/api/pricing', methods=['GET'])
def get_global_pricing():
    """Get all global model pricing"""
    try:
        with db_session_scope() as session:
            pricing_records = session.query(GlobalModelPricing).all()
            
            # Group by provider
            pricing_by_provider = {}
            for record in pricing_records:
                provider = record.provider
                if provider not in pricing_by_provider:
                    pricing_by_provider[provider] = []
                
                pricing_by_provider[provider].append(record.to_dict())
            
            return jsonify({
                'success': True,
                'pricing': pricing_by_provider,
                'total_count': len(pricing_records)
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/pricing', methods=['POST'])
def update_global_pricing():
    """Update or create global model pricing"""
    try:
        username = session.get('username')
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Expected format: { 'provider': 'openai', 'model_name': 'gpt-4', 'input_price_per_1m': '10.00', 'output_price_per_1m': '30.00' }
        provider = data.get('provider')
        model_name = data.get('model_name')
        input_price = data.get('input_price_per_1m')
        output_price = data.get('output_price_per_1m')
        notes = data.get('notes', '')
        
        if not provider or not model_name:
            return jsonify({'error': 'Provider and model_name are required'}), 400
        
        with db_session_scope() as db_session:
            # Check if pricing already exists
            existing = db_session.query(GlobalModelPricing).filter(
                GlobalModelPricing.provider == provider,
                GlobalModelPricing.model_name == model_name
            ).first()
            
            if existing:
                # Update existing
                existing.input_price_per_1m = input_price
                existing.output_price_per_1m = output_price
                existing.notes = notes
                existing.updated_by = username
                db_session.flush()
                
                log_admin_action(username, f"Updated pricing for {provider}/{model_name}")
                
                return jsonify({
                    'success': True,
                    'message': 'Pricing updated',
                    'pricing': existing.to_dict()
                })
            else:
                # Create new
                new_pricing = GlobalModelPricing(
                    provider=provider,
                    model_name=model_name,
                    input_price_per_1m=input_price,
                    output_price_per_1m=output_price,
                    notes=notes,
                    updated_by=username
                )
                db_session.add(new_pricing)
                db_session.flush()
                
                log_admin_action(username, f"Created pricing for {provider}/{model_name}")
                
                return jsonify({
                    'success': True,
                    'message': 'Pricing created',
                    'pricing': new_pricing.to_dict()
                })
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/pricing/<int:pricing_id>', methods=['DELETE'])
def delete_global_pricing(pricing_id):
    """Delete a global pricing entry"""
    try:
        username = session.get('username')
        
        with db_session_scope() as db_session:
            pricing = db_session.query(GlobalModelPricing).filter(
                GlobalModelPricing.id == pricing_id
            ).first()
            
            if not pricing:
                return jsonify({'error': 'Pricing not found'}), 404
            
            provider = pricing.provider
            model_name = pricing.model_name
            
            db_session.delete(pricing)
            db_session.flush()
            
            log_admin_action(username, f"Deleted pricing for {provider}/{model_name}")
            
            return jsonify({
                'success': True,
                'message': 'Pricing deleted'
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/pricing/upload', methods=['POST'])
def upload_pricing_excel():
    """Upload Excel file with pricing data for bulk import"""
    try:
        username = session.get('username')
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith(('.xlsx', '.xls')):
            return jsonify({'error': 'File must be Excel format (.xlsx or .xls)'}), 400
        
        # Parse Excel file
        try:
            import openpyxl
            workbook = openpyxl.load_workbook(file)
            sheet = workbook.active
            
            imported_count = 0
            errors = []
            
            # Expect headers: Provider, Model Name, Input ($/1M), Output ($/1M)
            # Skip header row
            for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                if not row or len(row) < 2:
                    continue
                
                provider = str(row[0]).strip() if row[0] else None
                model_name = str(row[1]).strip() if row[1] else None
                input_price = str(row[2]).strip() if len(row) > 2 and row[2] else ''
                output_price = str(row[3]).strip() if len(row) > 3 and row[3] else ''
                
                if not provider or not model_name:
                    errors.append(f"Row {row_idx}: Missing provider or model name")
                    continue
                
                # Clean up price values (remove $ signs, etc.)
                input_price = input_price.replace('$', '').replace(',', '').strip()
                output_price = output_price.replace('$', '').replace(',', '').strip()
                
                try:
                    with db_session_scope() as db_session:
                        # Check if exists
                        existing = db_session.query(GlobalModelPricing).filter(
                            GlobalModelPricing.provider == provider,
                            GlobalModelPricing.model_name == model_name
                        ).first()
                        
                        if existing:
                            # Update
                            existing.input_price_per_1m = input_price if input_price else None
                            existing.output_price_per_1m = output_price if output_price else None
                            existing.updated_by = username
                            db_session.flush()
                        else:
                            # Create
                            new_pricing = GlobalModelPricing(
                                provider=provider,
                                model_name=model_name,
                                input_price_per_1m=input_price if input_price else None,
                                output_price_per_1m=output_price if output_price else None,
                                updated_by=username
                            )
                            db_session.add(new_pricing)
                            db_session.flush()
                        
                        imported_count += 1
                        
                except Exception as e:
                    errors.append(f"Row {row_idx} ({provider}/{model_name}): {str(e)}")
            
            log_admin_action(username, f"Bulk imported {imported_count} pricing entries from Excel")
            
            result = {
                'success': True,
                'message': f'Import completed',
                'imported_count': imported_count
            }
            
            if errors:
                result['warnings'] = errors
            
            return jsonify(result)
            
        except ImportError:
            return jsonify({'error': 'openpyxl library not installed. Please install it.'}), 500
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error parsing Excel file: {str(e)}'}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
